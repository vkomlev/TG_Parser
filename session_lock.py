"""Межпроцессный lock на один session_file: только один процесс может использовать сессию."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

log = logging.getLogger("tg_parser.session_lock")

# Атомарное создание lock-файла: максимум попыток при перезахвате stale
_STALE_RETRY_MAX = 50
_STALE_RETRY_SLEEP = 0.05


def _lock_path(session_file: str) -> Path:
    """Путь к lock-файлу по имени сессии (однозначный и детерминированный)."""
    base = Path(session_file).resolve()
    return base.parent / (base.name + ".lock")


def _process_exists(pid: int) -> bool:
    """Проверить, что процесс с pid ещё работает (кроссплатформенно)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@contextmanager
def session_lock(session_file: str) -> Generator[bool, None, None]:
    """Контекстный менеджер: при входе пытается занять lock по session_file.

    Захват атомарный через exclusive create (O_CREAT|O_EXCL). При FileExistsError
    читаем PID из файла; если процесс мёртв — удаляем stale lock и повторяем в цикле.

    - Если lock занят другим живым процессом — yield False.
    - Если lock получен — yield True; при выходе lock-файл удаляется.

    Yields:
        True — lock получен. False — другой процесс держит lock.
    """
    path = _lock_path(session_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    lock_file = None

    try:
        for _ in range(_STALE_RETRY_MAX):
            try:
                # Атомарное создание: только один процесс создаст файл
                lock_file = open(path, "x", encoding="utf-8")
                break
            except FileExistsError:
                pass
            try:
                with open(path, "r", encoding="utf-8") as r:
                    pid_str = r.read().strip()
                if not pid_str:
                    time.sleep(_STALE_RETRY_SLEEP)
                    continue
                pid = int(pid_str)
            except (ValueError, OSError):
                pid = None
            if pid is not None and _process_exists(pid):
                log.warning(
                    "Сессия занята другим процессом: session_file=%s, lock_pid=%s",
                    session_file,
                    pid,
                    extra={"event": "session_lock_busy", "session_file": session_file, "lock_pid": pid},
                )
                yield False
                return
            path.unlink(missing_ok=True)
            time.sleep(_STALE_RETRY_SLEEP)

        if lock_file is None:
            yield False
            return

        lock_file.write(str(os.getpid()))
        lock_file.flush()
        acquired = True
        yield True
    finally:
        if lock_file is not None:
            try:
                lock_file.close()
            except OSError:
                pass
        if acquired and path.exists():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
