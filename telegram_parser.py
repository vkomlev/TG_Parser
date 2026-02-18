"""
Telegram Channel Parser
- Exports text + media to JSON
- Stores media on disk with channel/type structure
- Supports incremental updates via state.json
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.errors.rpcerrorlist import FileReferenceExpiredError
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, MessageMediaPoll


WINDOWS_BAD_CHARS = r'<>:"/\\|?*'


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date_utc(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    # date-only input in UTC midnight
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def sanitize_name(value: str) -> str:
    value = value.strip()
    value = "".join("_" if ch in WINDOWS_BAD_CHARS else ch for ch in value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._ ")
    return value or "unnamed"


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]


def limit_filename_base(base: str, max_len: int = 120) -> str:
    if len(base) <= max_len:
        return base
    suffix = short_hash(base)
    return f"{base[: max_len - 7]}_{suffix}"


# Ссылки на посты/каналы: https://t.me/channelname или https://t.me/channelname/123
_TELEGRAM_LINK_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)(?:/(\d+))?/?$",
    re.IGNORECASE,
)


def parse_telegram_link(link: str) -> Optional[Tuple[str, Optional[int]]]:
    """Извлечь из ссылки t.me/... username канала и опционально номер поста.

    Args:
        link: Ссылка вида https://t.me/AlgorithmPythonStruct/36 или t.me/channelname.

    Returns:
        Кортеж (username_канала, post_id или None) или None, если не ссылка.
    """
    s = (link or "").strip()
    m = _TELEGRAM_LINK_RE.match(s)
    if not m:
        return None
    username = m.group(1)
    post_id = int(m.group(2)) if m.group(2) else None
    return (username, post_id)


def channel_identifier_from_input(identifier: str) -> Tuple[str, Optional[int]]:
    """Нормализовать ввод: ссылка → (username для резолва, post_id); иначе (как есть, None).

    Args:
        identifier: Ссылка t.me/..., @username, или числовой id.

    Returns:
        (строка для get_entity, post_id или None).
    """
    parsed = parse_telegram_link(identifier)
    if parsed:
        username, post_id = parsed
        return (username if username.startswith("@") else f"@{username}", post_id)
    return (identifier.strip(), None)


def iso_from_telethon_date(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ModeConfig:
    batch_delay_min: float
    batch_delay_max: float
    flood_extra_delay: int
    max_retries: int
    media_concurrency: int


MODE_PRESETS = {
    "safe": ModeConfig(0.8, 1.5, 5, 5, 1),
    "normal": ModeConfig(0.3, 0.8, 3, 3, 2),
}


class JsonLogger:
    """JSONL-логгер с ротацией файлов.

    Пишет по одной JSON-строке на событие в:
    - `logs/run.log`
    - `logs/errors.log`
    """

    def __init__(self, logs_dir: Path, *, max_bytes: int = 2 * 1024 * 1024, backup_count: int = 10) -> None:
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Используем отдельные логгеры, чтобы не мешать глобальной конфигурации.
        key = str(logs_dir).replace("\\", "/")
        self._run_logger = logging.getLogger(f"tg_parser.json.run:{key}")
        self._err_logger = logging.getLogger(f"tg_parser.json.err:{key}")

        self._run_logger.setLevel(logging.INFO)
        self._err_logger.setLevel(logging.ERROR)
        self._run_logger.propagate = False
        self._err_logger.propagate = False

        fmt = logging.Formatter("%(message)s")

        if not self._run_logger.handlers:
            run_h = RotatingFileHandler(
                logs_dir / "run.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            run_h.setFormatter(fmt)
            self._run_logger.addHandler(run_h)

        if not self._err_logger.handlers:
            err_h = RotatingFileHandler(
                logs_dir / "errors.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            err_h.setFormatter(fmt)
            self._err_logger.addHandler(err_h)

    def _record(self, level: str, event: str, payload: Optional[Dict[str, Any]] = None) -> str:
        return json.dumps(
            {
                "ts": utc_now_iso(),
                "level": level,
                "event": event,
                "data": payload or {},
            },
            ensure_ascii=False,
        )

    def info(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._run_logger.info(self._record("INFO", event, payload))

    def error(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._err_logger.error(self._record("ERROR", event, payload))


class TelegramParser:
    def __init__(
        self,
        api_id: str,
        api_hash: str,
        session_file: str = "telegram_session",
        auth_state_dir: Optional[Path] = None,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_file = session_file
        self.auth_state_dir = auth_state_dir
        self.client: Optional[TelegramClient] = None
        self._log = logging.getLogger("tg_parser.core")

    def _auth_state_path(self) -> Optional[Path]:
        if not self.auth_state_dir:
            return None
        self.auth_state_dir.mkdir(parents=True, exist_ok=True)
        return self.auth_state_dir / "telegram_auth_state.json"

    async def connect(self) -> None:
        self.client = TelegramClient(self.session_file, int(self.api_id), self.api_hash)
        try:
            sess = getattr(self.client, "session", None)
            sess_name = sess.__class__.__name__ if sess else "None"
            sess_file = getattr(sess, "filename", None) if sess else None
            self._log.info("Сессия Telethon: %s (%s)", sess_name, sess_file or "без файла")
        except Exception:
            # Диагностика не должна ломать работу.
            pass
        await self.client.connect()

        if await self.client.is_user_authorized():
            return

        phone = os.getenv("TELEGRAM_PHONE")
        if not phone:
            raise RuntimeError("TELEGRAM_PHONE is required in .env for first authorization")

        code = (os.getenv("TELEGRAM_CODE") or os.getenv("TELEGRAM_LOGIN_CODE") or "").strip()
        state_path = self._auth_state_path()
        phone_code_hash: Optional[str] = None
        if state_path:
            state = self._load_json(state_path, {})
            phone_code_hash = state.get("phone_code_hash") if isinstance(state, dict) else None

        if not code:
            sent = await self.client.send_code_request(phone)
            if state_path:
                self._save_json(
                    state_path,
                    {
                        "created_at": utc_now_iso(),
                        "phone": phone,
                        "phone_code_hash": getattr(sent, "phone_code_hash", None),
                    },
                )
            # В среде без интерактива просим повторный запуск с кодом.
            raise RuntimeError(
                "Код отправлен в Telegram. Укажите TELEGRAM_CODE и повторите команду "
                "(хеш кода сохранён в logs/telegram_auth_state.json)."
            )

        try:
            if phone_code_hash:
                self._log.info("Вход: использую сохранённый phone_code_hash из auth state")
                await self.client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            else:
                self._log.info("Вход: phone_code_hash не найден, запрашиваю код заново")
                sent = await self.client.send_code_request(phone)
                await self.client.sign_in(phone=phone, code=code, phone_code_hash=getattr(sent, "phone_code_hash", None))
        except SessionPasswordNeededError:
            pwd = os.getenv("TELEGRAM_2FA_PASSWORD")
            if not pwd:
                pwd = input("Enter 2FA password: ").strip()
            await self.client.sign_in(password=pwd)
        finally:
            # После успешного входа очищаем auth state, чтобы не переиспользовать хеш.
            if state_path and state_path.exists() and await self.client.is_user_authorized():
                try:
                    state_path.unlink(missing_ok=True)
                except Exception:
                    pass

    async def disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()

    async def get_available_channels(self) -> List[Dict[str, Any]]:
        await self.connect()
        assert self.client

        dialogs = await self.client.get_dialogs()
        result = []
        for d in dialogs:
            if d.is_channel:
                result.append(
                    {
                        "id": d.id,
                        "username": getattr(d.entity, "username", None),
                        "title": d.name,
                    }
                )
        return result

    async def get_channel_info(self, link_or_identifier: str) -> Dict[str, Any]:
        """Получить id, username и title канала по ссылке t.me/..., @username или id.

        Args:
            link_or_identifier: Ссылка (https://t.me/channel/123), @username или числовой id.

        Returns:
            Словарь: id, username, title; если в ссылке был номер поста — post_id.
        """
        await self.connect()
        assert self.client
        entity = await self._resolve_entity(link_or_identifier)
        _, post_id = channel_identifier_from_input(link_or_identifier)
        channel_id = int(getattr(entity, "id", 0))
        username = getattr(entity, "username", None)
        title = getattr(entity, "title", None) or getattr(entity, "first_name", "")
        out: Dict[str, Any] = {
            "id": channel_id,
            "username": username,
            "title": title,
        }
        if post_id is not None:
            out["post_id"] = post_id
        return out

    async def _with_retries(self, coro_factory, logger: JsonLogger, mode_cfg: ModeConfig):
        retries = 0
        while True:
            try:
                return await coro_factory()
            except FileReferenceExpiredError:
                raise
            except FloodWaitError as e:
                wait_for = int(e.seconds) + mode_cfg.flood_extra_delay + random.randint(0, 2)
                logger.error("flood_wait", {"seconds": int(e.seconds), "sleep": wait_for})
                await asyncio.sleep(wait_for)
            except Exception as e:
                retries += 1
                if retries > mode_cfg.max_retries:
                    logger.error("retry_exhausted", {"error": str(e)})
                    raise
                backoff = 2 ** retries
                logger.error("retry", {"attempt": retries, "sleep": backoff, "error": str(e)})
                await asyncio.sleep(backoff)

    async def _resolve_entity(self, channel_identifier: str):
        """Резолв канала/чата по ссылке t.me/..., @username или числовому id."""
        assert self.client
        normalized, _ = channel_identifier_from_input(channel_identifier)
        try:
            if re.fullmatch(r"-?\d+", normalized or ""):
                return await self.client.get_entity(int(normalized))
            return await self.client.get_entity(normalized)
        except Exception:
            if not normalized.startswith("@"):
                return await self.client.get_entity(f"@{normalized}")
            raise

    def _find_or_create_export_dir(self, base_output: Path, channel_slug: str) -> Path:
        base_output.mkdir(parents=True, exist_ok=True)
        pattern = f"{channel_slug}__*"
        existing = sorted(base_output.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if existing:
            return existing[0]

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        target = base_output / f"{channel_slug}__{ts}"
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _save_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _media_type_and_ext(msg) -> Tuple[Optional[str], str, int]:
        # returns (media_type, extension, size)
        if isinstance(msg.media, MessageMediaPhoto):
            return "photo", ".jpg", 0
        if isinstance(msg.media, MessageMediaDocument) and msg.media.document:
            doc = msg.media.document
            mime = (doc.mime_type or "").lower()
            size = int(getattr(doc, "size", 0) or 0)
            original = None
            for a in doc.attributes:
                if hasattr(a, "file_name"):
                    original = a.file_name
                    break
            ext = Path(original).suffix if original and Path(original).suffix else ""
            if not ext:
                if "video" in mime:
                    ext = ".mp4"
                elif "image" in mime:
                    ext = ".jpg"
                else:
                    ext = ".bin"

            if "video" in mime:
                return "video", ext, size
            if "image" in mime:
                return "photo", ext, size
            return "document", ext, size
        return None, "", 0

    async def parse_channel(
        self,
        channel_identifier: str,
        output_dir: str,
        mode: str = "safe",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        keyword_filter: Optional[List[str]] = None,
        max_media_size_mb: Optional[int] = None,
        dry_run: bool = False,
        zip_output: bool = False,
        cleanup_temp: bool = True,
    ) -> Dict[str, Any]:
        await self.connect()
        assert self.client

        if mode not in MODE_PRESETS:
            raise ValueError("mode must be safe or normal")
        mode_cfg = MODE_PRESETS[mode]

        entity = await self._resolve_entity(channel_identifier)
        channel_id = int(getattr(entity, "id"))
        username = getattr(entity, "username", None)
        channel_slug = sanitize_name(username) if username else f"channel_{channel_id}"

        export_dir = self._find_or_create_export_dir(Path(output_dir), channel_slug)
        media_root = export_dir / "media"
        photos_dir = media_root / "photos"
        videos_dir = media_root / "videos"
        docs_dir = media_root / "documents"
        temp_dir = export_dir / ".tmp"
        for d in [photos_dir, videos_dir, docs_dir, temp_dir]:
            d.mkdir(parents=True, exist_ok=True)

        logs = JsonLogger(export_dir / "logs")
        logs.info("run_started", {"channel_identifier": channel_identifier, "mode": mode, "dry_run": dry_run})

        export_json_path = export_dir / "export.json"
        state_path = export_dir / "state.json"
        media_index_path = export_dir / "media-index.json"
        summary_path = export_dir / "summary.json"

        export_data = self._load_json(
            export_json_path,
            {
                "channel_info": {
                    "id": channel_id,
                    "username": username,
                    "title": getattr(entity, "title", None),
                },
                "messages": [],
                "export_date": utc_now_iso(),
                "total_messages": 0,
            },
        )

        existing_messages = {int(m["id"]) for m in export_data.get("messages", []) if "id" in m}
        state = self._load_json(
            state_path,
            {
                "channel_id": channel_id,
                "channel_username": username,
                "last_message_id": max(existing_messages) if existing_messages else 0,
                "last_update_at": None,
                "messages_total": len(existing_messages),
                "media_total": 0,
            },
        )
        media_index = self._load_json(media_index_path, {"sha256_to_path": {}})
        hash_index: Dict[str, str] = media_index.get("sha256_to_path", {})

        max_media_size_bytes = max_media_size_mb * 1024 * 1024 if max_media_size_mb else None
        from_dt = parse_date_utc(date_from)
        to_dt = parse_date_utc(date_to)
        keywords = [k.lower() for k in (keyword_filter or [])]

        new_messages: List[Dict[str, Any]] = []
        known_size_bytes = 0
        unknown_size_count = 0
        media_saved_count = 0
        media_skipped_size = 0
        media_dedup_hits = 0
        flood_wait_events = 0
        total_scanned = 0

        async def sleep_batch_jitter() -> None:
            await asyncio.sleep(random.uniform(mode_cfg.batch_delay_min, mode_cfg.batch_delay_max))

        offset_id = 0
        stop = False

        while not stop:
            async def fetch_history_batch():
                return await self.client(
                    GetHistoryRequest(
                        peer=entity,
                        offset_id=offset_id,
                        offset_date=None,
                        add_offset=0,
                        limit=100,
                        max_id=0,
                        min_id=0,
                        hash=0,
                    )
                )

            try:
                history = await self._with_retries(fetch_history_batch, logs, mode_cfg)
            except FloodWaitError:
                flood_wait_events += 1
                raise

            if not history.messages:
                break

            for msg in history.messages:
                total_scanned += 1
                msg_id = int(msg.id)

                # update mode: only new IDs
                if msg_id <= int(state.get("last_message_id", 0)) or msg_id in existing_messages:
                    continue

                if isinstance(msg.media, MessageMediaPoll):
                    continue

                msg_date_iso = iso_from_telethon_date(getattr(msg, "date", None))
                msg_date = msg.date.astimezone(timezone.utc) if getattr(msg, "date", None) else None

                # Оптимизация: история листается от новых к старым.
                # Если дошли до сообщений старше date_from — можно завершать выборку.
                if from_dt and msg_date and msg_date < from_dt:
                    stop = True
                    break
                if to_dt and msg_date and msg_date > to_dt:
                    continue

                text = msg.message or ""
                if keywords and not any(k in text.lower() for k in keywords):
                    continue

                media_files: List[Dict[str, Any]] = []

                mtype, ext, known_size = self._media_type_and_ext(msg)
                if mtype and known_size > 0:
                    known_size_bytes += known_size
                elif mtype:
                    unknown_size_count += 1

                if mtype and not dry_run:
                    if max_media_size_bytes and known_size and known_size > max_media_size_bytes:
                        media_skipped_size += 1
                    else:
                        if mtype == "photo":
                            target_dir = photos_dir
                        elif mtype == "video":
                            target_dir = videos_dir
                        else:
                            target_dir = docs_dir

                        original_name = None
                        if isinstance(msg.media, MessageMediaDocument) and msg.media.document:
                            for a in msg.media.document.attributes:
                                if hasattr(a, "file_name"):
                                    original_name = a.file_name
                                    break

                        if original_name:
                            clean_original = sanitize_name(original_name)
                            base = f"{msg_id}_{Path(clean_original).stem}"
                            base = limit_filename_base(base, 120)
                            final_name = f"{base}{Path(clean_original).suffix or ext}"
                        else:
                            base = limit_filename_base(str(msg_id), 120)
                            final_name = f"{base}{ext or '.bin'}"

                        temp_path = temp_dir / f"tmp_{msg_id}_{random.randint(1000, 9999)}"
                        media_to_dl = msg.media

                        async def dl_media(media=media_to_dl):
                            return await self.client.download_media(media, file=str(temp_path))

                        try:
                            downloaded_path_raw = await self._with_retries(dl_media, logs, mode_cfg)
                        except FileReferenceExpiredError:
                            logs.error("file_reference_expired", {"message_id": msg_id})
                            fresh = await self.client.get_messages(entity, ids=msg_id)
                            if fresh and getattr(fresh[0], "media", None):

                                async def dl_fresh():
                                    return await self.client.download_media(fresh[0].media, file=str(temp_path))

                                try:
                                    downloaded_path_raw = await self._with_retries(dl_fresh, logs, mode_cfg)
                                except Exception:
                                    logs.error("file_reference_retry_failed", {"message_id": msg_id})
                                    downloaded_path_raw = None
                                    media_files.append(
                                        {"type": mtype, "path": None, "filename": None, "error": "file_reference_expired"}
                                    )
                            else:
                                downloaded_path_raw = None
                                media_files.append(
                                    {"type": mtype, "path": None, "filename": None, "error": "file_reference_expired"}
                                )

                        if downloaded_path_raw:
                            downloaded_path = Path(downloaded_path_raw)
                            if downloaded_path.exists():
                                file_hash = self._sha256_file(downloaded_path)
                                existing_rel = hash_index.get(file_hash)
                                if existing_rel:
                                    media_dedup_hits += 1
                                    downloaded_path.unlink(missing_ok=True)
                                    media_files.append(
                                        {
                                            "type": mtype,
                                            "path": existing_rel,
                                            "filename": Path(existing_rel).name,
                                            "sha256": file_hash,
                                        }
                                    )
                                else:
                                    final_path = target_dir / final_name
                                    if final_path.exists():
                                        alt_base = limit_filename_base(f"{Path(final_name).stem}_{short_hash(file_hash)}", 120)
                                        final_path = target_dir / f"{alt_base}{final_path.suffix}"

                                    shutil.move(str(downloaded_path), str(final_path))
                                    rel_path = str(final_path.relative_to(export_dir)).replace("\\", "/")
                                    hash_index[file_hash] = rel_path
                                    media_saved_count += 1
                                    media_files.append(
                                        {
                                            "type": mtype,
                                            "path": rel_path,
                                            "filename": final_path.name,
                                            "size": final_path.stat().st_size,
                                            "sha256": file_hash,
                                        }
                                    )

                elif mtype and dry_run:
                    media_files.append(
                        {
                            "type": mtype,
                            "path": None,
                            "filename": None,
                            "size": known_size or None,
                        }
                    )

                fwd = None
                if msg.fwd_from:
                    fwd = {
                        "from_name": getattr(msg.fwd_from, "from_name", None),
                        "date": iso_from_telethon_date(getattr(msg.fwd_from, "date", None)),
                        "channel_post_id": getattr(msg.fwd_from, "channel_post", None),
                        "post_author": getattr(msg.fwd_from, "post_author", None),
                    }

                new_messages.append(
                    {
                        "id": msg_id,
                        "date": msg_date_iso,
                        "text": text,
                        "media_files": media_files,
                        "forwarded": fwd,
                        "reply_to_msg_id": msg.reply_to_msg_id,
                        "views": getattr(msg, "views", None),
                        "forwards": getattr(msg, "forwards", None),
                    }
                )

            if not dry_run and new_messages:
                all_messages = export_data.get("messages", []) + new_messages
                all_messages.sort(key=lambda m: int(m.get("id", 0)))
                export_data["messages"] = all_messages
                export_data["export_date"] = utc_now_iso()
                export_data["total_messages"] = len(all_messages)
                state["last_message_id"] = max(int(m.get("id", 0)) for m in all_messages)
                state["last_update_at"] = utc_now_iso()
                state["messages_total"] = len(all_messages)
                state["media_total"] = sum(len(m.get("media_files", [])) for m in all_messages)
                self._save_json(export_json_path, export_data)
                self._save_json(state_path, state)
                self._save_json(media_index_path, {"sha256_to_path": hash_index})

            if stop:
                break

            offset_id = history.messages[-1].id
            await sleep_batch_jitter()

        # merge/update
        if not dry_run and new_messages:
            all_messages = export_data.get("messages", []) + new_messages
            all_messages.sort(key=lambda m: int(m.get("id", 0)))
            export_data["messages"] = all_messages
            export_data["export_date"] = utc_now_iso()
            export_data["total_messages"] = len(all_messages)

            state["last_message_id"] = max([int(m.get("id", 0)) for m in all_messages], default=0)
            state["last_update_at"] = utc_now_iso()
            state["messages_total"] = len(all_messages)
            state["media_total"] = sum(len(m.get("media_files", [])) for m in all_messages)

            self._save_json(export_json_path, export_data)
            self._save_json(state_path, state)
            self._save_json(media_index_path, {"sha256_to_path": hash_index})

        summary = {
            "run_at": utc_now_iso(),
            "channel_id": channel_id,
            "channel_username": username,
            "mode": mode,
            "dry_run": dry_run,
            "date_from": date_from,
            "date_to": date_to,
            "scanned_messages": total_scanned,
            "new_messages": len(new_messages),
            "media_saved": media_saved_count,
            "media_skipped_by_size": media_skipped_size,
            "media_dedup_hits": media_dedup_hits,
            "known_size_mb": round(known_size_bytes / (1024 * 1024), 3),
            "unknown_size_count": unknown_size_count,
            "flood_wait_events": flood_wait_events,
            "export_dir": str(export_dir),
        }
        self._save_json(summary_path, summary)

        archive_path = None
        if zip_output and not dry_run:
            archive_path = export_dir.with_suffix(".zip")
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in export_dir.rglob("*"):
                    if p.is_file() and ".tmp" not in p.parts:
                        zf.write(p, p.relative_to(export_dir.parent))

        if cleanup_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        logs.info("run_finished", summary)

        return {
            "summary": summary,
            "export_dir": str(export_dir),
            "export_json": str(export_json_path),
            "state_json": str(state_path),
            "media_index_json": str(media_index_path),
            "summary_json": str(summary_path),
            "archive": str(archive_path) if archive_path else None,
        }

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
