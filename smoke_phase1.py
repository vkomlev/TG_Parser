#!/usr/bin/env python3
"""
Смоук-тесты Phase 1: коды выхода и partial_failure.

1. Обязательные в CI: --unit-only (exit-коды/partial без Telegram).
2. Интеграционные 2–4: запуск отдельно, с сессией telegram_session_smoke,
   без двойного connect (connect() вызывается только внутри parse_channel()).

Запуск из корня проекта (.venv активирован):
  python smoke_phase1.py --unit-only   # только юнит, для CI
  python smoke_phase1.py               # юнит + интеграционные 2–4 (.env + telegram_session_smoke; при первом запуске интеграций может потребоваться авторизация для сессии smoke)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

from telegram_parser import (
    MODE_PRESETS,
    TelegramParser,
    ModeConfig,
)
from telethon.errors.rpcerrorlist import FileReferenceExpiredError

from exit_codes import EXIT_PARTIAL
from telegram_parser_skill import run as cli_run
from telegram_parser_skill import build_parser

# канал с медиа для тестов 2–4
TEST_CHANNEL = "https://t.me/AlgorithmPythonStruct"
OUT_DIR = Path(__file__).parent / "out_smoke_phase1"


def _reset_case_output(case_dir: Path) -> None:
    """Удалить артефакты предыдущих прогонов тест-кейса."""
    shutil.rmtree(case_dir, ignore_errors=True)


async def test_cli_exit_partial_with_mock() -> bool:
    """Без Telegram: при result.partial_failure=True CLI возвращает EXIT_PARTIAL (2)."""
    fake_result = {
        "summary": {"partial_failure": True, "media_errors_count": 1},
        "partial_failure": True,
        "export_dir": "",
        "export_json": "",
        "state_json": "",
        "media_index_json": "",
        "summary_json": "",
        "archive": None,
    }
    args = build_parser().parse_args(["parse", "--channel", "https://t.me/dummy", "--output-dir", str(OUT_DIR)])
    with patch.object(TelegramParser, "connect", new_callable=AsyncMock), patch.object(
        TelegramParser, "disconnect", new_callable=AsyncMock
    ), patch.object(TelegramParser, "parse_channel", new_callable=AsyncMock, return_value=fake_result):
        code = await cli_run(args)
    return code == EXIT_PARTIAL


def _get_media_errors_from_export(export_dir: str) -> list[str]:
    """Собрать все media_files[].error из export.json в export_dir."""
    export_path = Path(export_dir) / "export.json"
    if not export_path.exists():
        return []
    data = json.loads(export_path.read_text(encoding="utf-8"))
    errors = []
    for msg in data.get("messages", []):
        for m in msg.get("media_files", []):
            if m.get("error"):
                errors.append(m["error"])
    return errors


async def test2_file_reference_expired(parser: TelegramParser) -> bool:
    """parse с file_reference_expired → partial_failure, media_errors_count>0, error=file_reference_expired."""
    # Делаем поведение теста быстрым и детерминированным:
    # при любой ошибке мока не уходим в долгий backoff retry.
    case_dir = OUT_DIR / "t2"
    _reset_case_output(case_dir)

    safe_orig = MODE_PRESETS["safe"]
    MODE_PRESETS["safe"] = ModeConfig(
        safe_orig.batch_delay_min,
        safe_orig.batch_delay_max,
        safe_orig.flood_extra_delay,
        0,  # max_retries
        safe_orig.media_concurrency,
        safe_orig.media_download_timeout_sec,
    )
    try:
        async def _mock_download(*args, **kwargs):
            raise FileReferenceExpiredError(request=None)

        with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(
            parser.client, "download_media", side_effect=_mock_download
        ):
            result = await parser.parse_channel(
                channel_identifier=TEST_CHANNEL,
                output_dir=str(case_dir),
                mode="safe",
                dry_run=False,
            )
        ok = (
            result.get("partial_failure") is True
            and result["summary"]["media_errors_count"] >= 1
        )
        errors = _get_media_errors_from_export(result["export_dir"])
        ok = ok and "file_reference_expired" in errors
        return ok
    finally:
        MODE_PRESETS["safe"] = safe_orig


async def test3_download_timeout(parser: TelegramParser) -> bool:
    """parse с таймаутом загрузки медиа → partial_failure, error=download_timeout."""
    # Чтобы не ждать 5 retry с backoff, подменяем пресет на max_retries=0.
    case_dir = OUT_DIR / "t3"
    _reset_case_output(case_dir)

    safe_orig = MODE_PRESETS["safe"]
    MODE_PRESETS["safe"] = ModeConfig(
        safe_orig.batch_delay_min,
        safe_orig.batch_delay_max,
        safe_orig.flood_extra_delay,
        0,  # max_retries
        safe_orig.media_concurrency,
        safe_orig.media_download_timeout_sec,
    )
    try:
        async def _mock_download(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(
            parser.client, "download_media", side_effect=_mock_download
        ):
            result = await parser.parse_channel(
                channel_identifier=TEST_CHANNEL,
                output_dir=str(case_dir),
                mode="safe",
                dry_run=False,
            )
        ok = (
            result.get("partial_failure") is True
            and result["summary"]["media_errors_count"] >= 1
        )
        errors = _get_media_errors_from_export(result["export_dir"])
        ok = ok and "download_timeout" in errors
        return ok
    finally:
        MODE_PRESETS["safe"] = safe_orig


async def test4_retry_exhausted(parser: TelegramParser) -> bool:
    """parse с исчерпанием retry по другой ошибке → partial_failure, error=retry_exhausted."""
    case_dir = OUT_DIR / "t4"
    _reset_case_output(case_dir)

    safe_orig = MODE_PRESETS["safe"]
    MODE_PRESETS["safe"] = ModeConfig(
        safe_orig.batch_delay_min,
        safe_orig.batch_delay_max,
        safe_orig.flood_extra_delay,
        0,
        safe_orig.media_concurrency,
        safe_orig.media_download_timeout_sec,
    )
    try:
        async def _mock_download(*args, **kwargs):
            raise ConnectionError("mock connection error")

        with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(
            parser.client, "download_media", side_effect=_mock_download
        ):
            result = await parser.parse_channel(
                channel_identifier=TEST_CHANNEL,
                output_dir=str(case_dir),
                mode="safe",
                dry_run=False,
            )
        ok = (
            result.get("partial_failure") is True
            and result["summary"]["media_errors_count"] >= 1
        )
        errors = _get_media_errors_from_export(result["export_dir"])
        ok = ok and "retry_exhausted" in errors
        return ok
    finally:
        MODE_PRESETS["safe"] = safe_orig


async def main() -> int:
    load_dotenv(Path(__file__).parent / ".env")
    if "--unit-only" in sys.argv:
        sys.argv.remove("--unit-only")
        os.environ.setdefault("TELEGRAM_API_ID", "1")
        os.environ.setdefault("TELEGRAM_API_HASH", "x")
        ok = await test_cli_exit_partial_with_mock()
        print("  PASS: CLI exit 2 on partial_failure (mocked)" if ok else "  FAIL: CLI exit 2 on partial_failure (mocked)")
        return 0 if ok else 1

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        print("SKIP: TELEGRAM_API_ID/TELEGRAM_API_HASH required for tests 2–4")
        return 0

    # Юнит-тест выхода 2 без Telegram
    unit_ok = await test_cli_exit_partial_with_mock()
    print("  " + ("PASS" if unit_ok else "FAIL") + ": CLI exit 2 on partial_failure (mocked)")

    # Отдельная сессия для интеграционных тестов (не боевая telegram_session).
    parser = TelegramParser(
        api_id=api_id,
        api_hash=api_hash,
        session_file="telegram_session_smoke",
        auth_state_dir=Path(__file__).parent / "logs",
    )
    try:
        await asyncio.wait_for(parser.connect(), timeout=30.0)
    except asyncio.TimeoutError:
        print("SKIP: подключение к Telegram превысило 30 с. Интеграционные тесты 2–4 пропущены.")
        print("Для быстрой проверки без сети: python smoke_phase1.py --unit-only")
        return 0
    except RuntimeError as e:
        msg = str(e)
        if "TELEGRAM_CODE" in msg or "TELEGRAM_PHONE" in msg or "Код отправлен" in msg or "authorization" in msg.lower():
            print("SKIP: сессия telegram_session_smoke не авторизована. Интеграционные тесты 2–4 пропущены.")
            print("Вариант 1 — скопировать боевую сессию (не нужен код):")
            print("  copy telegram_session.session telegram_session_smoke.session")
            print("Вариант 2 — авторизовать smoke вручную: запуск с --session-file telegram_session_smoke и ввод кода при запросе.")
            return 0
        raise

    results = []
    # Test 2
    try:
        ok = await test2_file_reference_expired(parser)
        results.append(("2 file_reference_expired", ok))
    except Exception as e:
        results.append(("2 file_reference_expired", False))
        print(f"Test 2 error: {e}")
    # Test 3
    try:
        ok = await test3_download_timeout(parser)
        results.append(("3 download_timeout", ok))
    except Exception as e:
        results.append(("3 download_timeout", False))
        print(f"Test 3 error: {e}")
    # Test 4
    try:
        ok = await test4_retry_exhausted(parser)
        results.append(("4 retry_exhausted", ok))
    except Exception as e:
        results.append(("4 retry_exhausted", False))
        print(f"Test 4 error: {e}")

    try:
        await parser.disconnect()
    except Exception as e:
        print(f"Disconnect warning: {e}")

    failed = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    if failed:
        print("FAILED:", failed)
        return 1
    print("All Phase 1 smoke tests (2–4) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
