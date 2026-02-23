#!/usr/bin/env python3
"""
Смоук-тесты Phase 2: run_id, error_code (CONFIG_ERROR, AUTH_ERROR, EXTERNAL_API_ERROR, PARTIAL_FAILURE, RATE_LIMIT).

Разделение:
- --unit-only (моки, для CI): тесты 3, 5, 6, 7.
- Интеграционные (с Telegram): тесты 1, 2, 4.

Запуск из корня проекта (.venv):
  python tests/smoke_phase2.py --unit-only
  python tests/smoke_phase2.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

from telegram_parser import (
    MODE_PRESETS,
    TelegramParser,
    ModeConfig,
)
from telegram_parser import TelegramParser as _Parser
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import FileReferenceExpiredError
from telethon.tl.functions.messages import GetHistoryRequest

from exit_codes import EXIT_PARTIAL

TEST_CHANNEL = "https://t.me/AlgorithmPythonStruct"
OUT_DIR = PROJECT_ROOT / "tests" / "out" / "smoke_phase2"
APP_LOGS = PROJECT_ROOT / "logs"
APP_ERRORS_LOG = APP_LOGS / "errors.log"
APP_APP_LOG = APP_LOGS / "app.log"


def _reset_case_output(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def test3_config_error_in_errors_log() -> bool:
    """Запуск resolve без --channel → exit 1, в новых строках логов есть error_code=CONFIG_ERROR."""
    app_len_before = APP_APP_LOG.stat().st_size if APP_APP_LOG.exists() else 0
    err_len_before = APP_ERRORS_LOG.stat().st_size if APP_ERRORS_LOG.exists() else 0

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "telegram_parser_skill.py"), "resolve"],
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode != 1:
        return False

    def _new_tail(path: Path, start: int) -> str:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(start)
            return f.read()

    new_err = _new_tail(APP_ERRORS_LOG, err_len_before)
    new_app = _new_tail(APP_APP_LOG, app_len_before)
    if "CONFIG_ERROR" in new_err or "CONFIG_ERROR" in new_app:
        return True
    return False


async def test5_external_api_error_in_export_logs(parser: TelegramParser) -> bool:
    """Мок download_media на timeout → в export logs/errors.log есть data.error_code=EXTERNAL_API_ERROR."""
    case_dir = OUT_DIR / "t5"
    _reset_case_output(case_dir)
    safe_orig = MODE_PRESETS["safe"]
    MODE_PRESETS["safe"] = ModeConfig(safe_orig.batch_delay_min, safe_orig.batch_delay_max, safe_orig.flood_extra_delay, 0, safe_orig.media_concurrency, safe_orig.media_download_timeout_sec)
    try:
        async def _mock_download(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(parser.client, "download_media", side_effect=_mock_download):
            result = await parser.parse_channel(channel_identifier=TEST_CHANNEL, output_dir=str(case_dir), mode="safe", dry_run=False)
        errors_log = Path(result["export_dir"]) / "logs" / "errors.log"
        if not errors_log.exists():
            return False
        for line in errors_log.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if obj.get("data", {}).get("error_code") == "EXTERNAL_API_ERROR":
                    return True
            except json.JSONDecodeError:
                continue
        return False
    finally:
        MODE_PRESETS["safe"] = safe_orig


async def test6_partial_failure_in_run_log(parser: TelegramParser) -> bool:
    """Partial run (мок медиа-ошибок) → exit 2, summary.partial_failure=true, run_finished в run.log с error_code=PARTIAL_FAILURE."""
    case_dir = OUT_DIR / "t6"
    _reset_case_output(case_dir)
    safe_orig = MODE_PRESETS["safe"]
    MODE_PRESETS["safe"] = ModeConfig(safe_orig.batch_delay_min, safe_orig.batch_delay_max, safe_orig.flood_extra_delay, 0, safe_orig.media_concurrency, safe_orig.media_download_timeout_sec)
    try:
        async def _mock_download(*args, **kwargs):
            raise FileReferenceExpiredError(request=None)

        with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(parser.client, "download_media", side_effect=_mock_download):
            result = await parser.parse_channel(channel_identifier=TEST_CHANNEL, output_dir=str(case_dir), mode="safe", dry_run=False)
        if not result.get("partial_failure") or not result.get("summary", {}).get("partial_failure"):
            return False
        run_log = Path(result["export_dir"]) / "logs" / "run.log"
        if not run_log.exists():
            return False
        for line in run_log.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if obj.get("event") == "run_finished" and obj.get("data", {}).get("error_code") == "PARTIAL_FAILURE":
                    return True
            except json.JSONDecodeError:
                continue
        return False
    finally:
        MODE_PRESETS["safe"] = safe_orig


async def test7_rate_limit_in_export_logs(parser: TelegramParser) -> bool:
    """Мок FloodWaitError при первом запросе истории → запись flood_wait с error_code=RATE_LIMIT в export errors.log."""
    case_dir = OUT_DIR / "t7"
    _reset_case_output(case_dir)
    call_count = [0]
    raised_on_history = [False]
    client_cls = type(parser.client)
    original_call = client_cls.__call__

    class FloodWaitWithSeconds(FloodWaitError):
        def __init__(self):
            super().__init__(None)
            self.seconds = 1

    async def patched_call(this, request, *args, **kwargs):
        if this is parser.client:
            call_count[0] += 1
            if (not raised_on_history[0]) and isinstance(request, GetHistoryRequest):
                raised_on_history[0] = True
                raise FloodWaitWithSeconds()
        return await original_call(this, request, *args, **kwargs)

    with patch.object(parser, "connect", new_callable=AsyncMock), patch.object(client_cls, "__call__", new=patched_call):
        result = await parser.parse_channel(channel_identifier=TEST_CHANNEL, output_dir=str(case_dir), mode="safe", dry_run=True)
    export_dir = result.get("export_dir") or str(case_dir)
    errors_log = Path(export_dir) / "logs" / "errors.log"
    if not errors_log.exists():
        return False
    for line in errors_log.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("event") == "flood_wait" and obj.get("data", {}).get("error_code") == "RATE_LIMIT":
                return True
        except json.JSONDecodeError:
            continue
    return False


def test1_run_id_in_app_log() -> bool:
    """parse --dry-run → в logs/app.log у записей один и тот же [run_id] в рамках запуска."""
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "telegram_parser_skill.py"), "parse", "--channel", TEST_CHANNEL, "--dry-run", "--output-dir", str(OUT_DIR)],
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        return False
    if not APP_APP_LOG.exists():
        return False
    content = APP_APP_LOG.read_text(encoding="utf-8", errors="replace")
    last_part = content[-5000:] if len(content) > 5000 else content
    matches = re.findall(r"\[([a-f0-9]{8})\]", last_part)
    return len(matches) >= 1 and len(set(matches)) == 1


def test2_run_id_in_export_and_summary() -> bool:
    """Тот же dry-run → в out/.../logs/run.log и summary run_id совпадают."""
    export_dirs = list(OUT_DIR.glob("*__*"))
    if not export_dirs:
        return False
    export_dir = max(export_dirs, key=lambda p: p.stat().st_mtime)
    summary_path = export_dir / "summary.json"
    run_log_path = export_dir / "logs" / "run.log"
    if not summary_path.exists() or not run_log_path.exists():
        return False
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_id_summary = summary.get("run_id")
    if run_id_summary is None:
        return False
    for line in run_log_path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("data", {}).get("run_id") == run_id_summary:
                return True
        except json.JSONDecodeError:
            continue
    return False


def test4_auth_error_in_errors_log() -> bool:
    """Неавторизованная сессия → exit 1, в logs/errors.log есть error_code=AUTH_ERROR."""
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "telegram_parser_skill.py"), "parse", "--channel", TEST_CHANNEL, "--session-file", "telegram_session_nonexistent_auth_test"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 1:
        return False
    if not APP_ERRORS_LOG.exists():
        return False
    content = APP_ERRORS_LOG.read_text(encoding="utf-8", errors="replace")
    return "AUTH_ERROR" in content


async def run_unit_tests() -> list[tuple[str, bool]]:
    results = []
    try:
        ok = test3_config_error_in_errors_log()
        results.append(("3 CONFIG_ERROR в errors.log", ok))
    except Exception as e:
        results.append(("3 CONFIG_ERROR в errors.log", False))
        print(f"Test 3 error: {e}")

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        results.append(("5 EXTERNAL_API_ERROR в export logs", False))
        results.append(("6 PARTIAL_FAILURE в run_finished", False))
        results.append(("7 RATE_LIMIT flood_wait", False))
        return results

    parser = _Parser(api_id=api_id, api_hash=api_hash, session_file="telegram_session_smoke", auth_state_dir=PROJECT_ROOT / "logs")
    try:
        await asyncio.wait_for(parser.connect(), timeout=30.0)
    except (asyncio.TimeoutError, RuntimeError) as e:
        print(f"SKIP 5–7: {e}")
        results.append(("5 EXTERNAL_API_ERROR в export logs", False))
        results.append(("6 PARTIAL_FAILURE в run_finished", False))
        results.append(("7 RATE_LIMIT flood_wait", False))
        return results

    for name, coro in [
        ("5 EXTERNAL_API_ERROR в export logs", test5_external_api_error_in_export_logs(parser)),
        ("6 PARTIAL_FAILURE в run_finished", test6_partial_failure_in_run_log(parser)),
        ("7 RATE_LIMIT flood_wait", test7_rate_limit_in_export_logs(parser)),
    ]:
        try:
            ok = await coro
            results.append((name, ok))
        except Exception as e:
            results.append((name, False))
            print(f"  {name} error: {e}")

    try:
        await parser.disconnect()
    except Exception:
        pass
    return results


def run_integration_tests() -> list[tuple[str, bool]]:
    results = []
    try:
        ok = test1_run_id_in_app_log()
        results.append(("1 run_id в app.log", ok))
    except Exception as e:
        results.append(("1 run_id в app.log", False))
        print(f"Test 1 error: {e}")
    try:
        ok = test2_run_id_in_export_and_summary()
        results.append(("2 run_id в export/summary", ok))
    except Exception as e:
        results.append(("2 run_id в export/summary", False))
        print(f"Test 2 error: {e}")
    try:
        ok = test4_auth_error_in_errors_log()
        results.append(("4 AUTH_ERROR в errors.log", ok))
    except Exception as e:
        results.append(("4 AUTH_ERROR в errors.log", False))
        print(f"Test 4 error: {e}")
    return results


async def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    unit_only = "--unit-only" in sys.argv
    if unit_only:
        sys.argv.remove("--unit-only")
    unit_results = await run_unit_tests()
    for name, ok in unit_results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    if unit_only:
        failed = [n for n, ok in unit_results if not ok]
        return 1 if failed else 0
    int_results = run_integration_tests()
    for name, ok in int_results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    all_results = unit_results + int_results
    failed = [n for n, ok in all_results if not ok]
    if failed:
        print("FAILED:", failed)
        return 1
    print("All Phase 2 smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
