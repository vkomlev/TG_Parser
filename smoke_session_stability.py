#!/usr/bin/env python3
"""
Смоук-тесты стабилизации парсера (ТЗ: lock, retry connect, наблюдаемость).
- Unit: session_lock (acquire/release, stale lock, занятая сессия).
- Unit: connect retry на database is locked.
- Интеграционный: два процесса с одним session_file — второй завершается с SESSION_LOCKED.

Запуск из корня проекта:
  python smoke_session_stability.py              # все тесты
  python smoke_session_stability.py --hold-lock NAME   # режим для интеграции: занять lock и спать
  python smoke_session_stability.py --try-lock NAME    # попытка занять lock, exit 0/1
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# Режимы для интеграционного теста (subprocess)
if len(sys.argv) >= 3 and sys.argv[1] == "--hold-lock":
    from session_lock import session_lock
    name = sys.argv[2]
    with session_lock(name) as acquired:
        if not acquired:
            sys.exit(1)
        time.sleep(5)
    sys.exit(0)

if len(sys.argv) >= 3 and sys.argv[1] == "--try-lock":
    from session_lock import session_lock
    name = sys.argv[2]
    with session_lock(name) as acquired:
        sys.exit(0 if acquired else 1)
    sys.exit(0)

# Обычный запуск тестов
import sqlite3
from unittest.mock import AsyncMock

import telegram_parser as _telegram_parser_mod
from session_lock import _lock_path, session_lock
from telegram_parser import TelegramParser


def test_session_lock_acquire_release() -> bool:
    """Один процесс: acquire → release → снова acquire — оба раза True."""
    name = "smoke_test_lock_1"
    lock_path = _lock_path(name)
    lock_path.unlink(missing_ok=True)
    try:
        with session_lock(name) as a:
            if not a:
                return False
        with session_lock(name) as b:
            if not b:
                return False
        return True
    finally:
        lock_path.unlink(missing_ok=True)


def test_session_lock_stale_pid() -> bool:
    """Lock-файл с несуществующим PID — считаем stale, занимаем lock."""
    name = "smoke_test_lock_stale"
    lock_path = _lock_path(name)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("99999999", encoding="utf-8")  # несуществующий PID
    try:
        with session_lock(name) as a:
            return a is True
    finally:
        lock_path.unlink(missing_ok=True)


def test_session_lock_busy_same_pid() -> bool:
    """Lock-файл с текущим PID (имитация «другой процесс») — считаем занятым, yield False."""
    name = "smoke_test_lock_busy"
    lock_path = _lock_path(name)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    try:
        with session_lock(name) as a:
            return a is False
    finally:
        lock_path.unlink(missing_ok=True)


async def test_connect_retry_database_locked() -> bool:
    """connect() при database is locked — retry с backoff, затем успех."""
    parser = TelegramParser(api_id="1", api_hash="x", session_file="nonexistent_session_file")
    call_count = 0

    async def mock_connect():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise sqlite3.OperationalError("database is locked")
        return None

    async def noop_sleep(_sec: float) -> None:
        return

    mock_client = AsyncMock()
    mock_client.connect = AsyncMock(side_effect=mock_connect)
    mock_client.is_user_authorized = AsyncMock(return_value=True)
    parser.client = mock_client

    old_sleep = _telegram_parser_mod.asyncio.sleep
    _telegram_parser_mod.asyncio.sleep = noop_sleep
    try:
        try:
            await parser.connect()
        except Exception:
            return False
        return call_count == 3
    finally:
        _telegram_parser_mod.asyncio.sleep = old_sleep


def test_integration_two_processes_same_session() -> bool:
    """Два процесса с одним session_file: первый держит lock, второй выходит с кодом 1."""
    root = Path(__file__).parent
    session_name = "smoke_test_concurrent_session"
    lock_path = _lock_path(session_name)
    lock_path.unlink(missing_ok=True)

    try:
        proc_hold = subprocess.Popen(
            [sys.executable, str(root / "smoke_session_stability.py"), "--hold-lock", session_name],
            cwd=str(root),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)
        proc_try = subprocess.run(
            [sys.executable, str(root / "telegram_parser_skill.py"), "parse", "--channel", "dummy", "--session-file", session_name],
            cwd=str(root),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=5,
        )
        proc_hold.terminate()
        proc_hold.wait(timeout=3)

        if proc_try.returncode != 1:
            return False
        err = (proc_try.stderr or "") + (proc_try.stdout or "")
        if "session" in err.lower() and ("lock" in err.lower() or "SESSION_LOCKED" in err or "Error:" in err):
            return True
        return "session is locked" in err or "SESSION_LOCKED" in err
    finally:
        lock_path.unlink(missing_ok=True)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-integration", action="store_true", help="Пропустить интеграционный тест (два процесса)")
    args, _ = ap.parse_known_args()

    results = []

    results.append(("session_lock acquire/release", test_session_lock_acquire_release()))
    results.append(("session_lock stale PID", test_session_lock_stale_pid()))
    results.append(("session_lock busy same PID", test_session_lock_busy_same_pid()))
    results.append(("connect retry database_locked", asyncio.run(test_connect_retry_database_locked())))
    if not args.no_integration:
        results.append(("integration two processes same session", test_integration_two_processes_same_session()))

    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    failed = [n for n, ok in results if not ok]
    if failed:
        print("FAILED:", failed)
        return 1
    print("All session stability smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
