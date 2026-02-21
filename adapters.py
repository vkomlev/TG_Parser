"""
Phase 3: протоколы SourceAdapter и DestinationAdapter, фасады над текущим парсером и экспортом.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from contracts import (
    ContentItem,
    content_item_to_tg_message,
    tg_message_to_content_item,
)
from telegram_parser import TelegramParser, utc_now_iso


@runtime_checkable
class SourceAdapter(Protocol):
    """Источник сообщений: возвращает нормализованные ContentItem."""

    async def fetch_messages(
        self,
        channel_identifier: str,
        output_dir: str,
        **kwargs: Any,
    ) -> List[ContentItem]:
        """Загрузить сообщения и вернуть список нормализованных элементов."""
        ...


class TelegramSourceAdapter:
    """Фасад над TelegramParser: вызывает parse_channel и маппит результат в ContentItem."""

    def __init__(self, parser: TelegramParser):
        self._parser = parser

    async def fetch_messages(
        self,
        channel_identifier: str,
        output_dir: str,
        **kwargs: Any,
    ) -> List[ContentItem]:
        result = await self._parser.parse_channel(
            channel_identifier=channel_identifier,
            output_dir=output_dir,
            **{k: v for k, v in kwargs.items() if k in ("mode", "date_from", "date_to", "keyword_filter", "max_media_size_mb", "dry_run", "zip_output", "cleanup_temp", "run_id")},
        )
        channel_id = result.get("summary", {}).get("channel_id") or ""
        username = result.get("summary", {}).get("channel_username") or ""
        source_id = f"telegram:{username or channel_id}"
        new_messages = result.get("new_messages")
        if new_messages is not None:
            return [tg_message_to_content_item(m, source_id) for m in new_messages]
        export_dir = Path(result.get("export_dir", ""))
        export_json = export_dir / "export.json"
        if not export_json.exists():
            return []
        data = json.loads(export_json.read_text(encoding="utf-8"))
        messages = data.get("messages") or []
        return [tg_message_to_content_item(m, source_id) for m in messages]


@runtime_checkable
class DestinationAdapter(Protocol):
    """Приёмник: публикует нормализованные элементы (локальный экспорт, VK, WP и т.д.)."""

    def publish_batch(self, items: List[ContentItem], export_dir: Path, **kwargs: Any) -> None:
        """Записать пакет элементов в назначение."""
        ...


class LocalExportDestinationAdapter:
    """Локальный экспорт: запись в export.json и учёт медиа (пути уже в ContentItem)."""

    def publish_batch(
        self,
        items: List[ContentItem],
        export_dir: Path,
        *,
        append: bool = True,
        channel_info: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        export_json = export_dir / "export.json"
        if append and export_json.exists():
            data = json.loads(export_json.read_text(encoding="utf-8"))
            existing = data.get("messages") or []
        else:
            data = {"messages": [], "export_date": None, "total_messages": 0}
            if channel_info:
                data["channel_info"] = channel_info
            existing = []
        new_messages = [content_item_to_tg_message(item) for item in items]
        all_messages = existing + new_messages

        def _msg_sort_key(m: Dict[str, Any]) -> tuple:
            id_ = m.get("id")
            if id_ is None:
                return (0, 0)
            if isinstance(id_, (int, float)):
                return (0, id_)
            if isinstance(id_, str) and id_.isdigit():
                return (0, int(id_))
            return (1, str(id_))

        all_messages.sort(key=_msg_sort_key)
        data["messages"] = all_messages
        data["total_messages"] = len(all_messages)
        data["export_date"] = utc_now_iso()
        export_dir.mkdir(parents=True, exist_ok=True)
        export_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
