"""Настройка логирования приложения.

Логи пишутся в папку `logs/` рядом с файлом и ротируются по размеру.
Поддерживаются run_id (correlation id) и error_code в каждой записи.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Контекст run_id для текущего запроса (устанавливается в main()).
_run_id_ctx: ContextVar[Optional[str]] = ContextVar("run_id", default=None)


def set_run_id(run_id: Optional[str]) -> None:
    """Установить run_id для текущего контекста (логи)."""
    _run_id_ctx.set(run_id)


def get_run_id() -> Optional[str]:
    """Текущий run_id из контекста."""
    return _run_id_ctx.get()


class RunIdFilter(logging.Filter):
    """Добавляет run_id и error_code в каждую запись лога (из контекста и extra)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", None) or _run_id_ctx.get() or "-"
        record.error_code = getattr(record, "error_code", None) or "-"
        return True


def setup_app_logging(
    logs_dir: Path,
    level: int = logging.INFO,
    run_id: Optional[str] = None,
) -> None:
    """Настроить логирование в `logs/app.log` с ротацией.

    Args:
        logs_dir: Каталог для логов.
        level: Уровень логирования (по умолчанию INFO).
        run_id: Correlation id для этого запуска (добавляется во все записи).

    Returns:
        None.
    """
    if run_id is not None:
        set_run_id(run_id)

    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Идемпотентность: не добавляем хендлеры повторно.
    for h in root.handlers:
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "").endswith("app.log"):
            return

    run_filter = RunIdFilter()

    class AppLogFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            base = super().format(record)
            if getattr(record, "error_code", "-") != "-":
                base += f" error_code={record.error_code}"
            return base

    formatter = AppLogFormatter("%(asctime)sZ %(levelname)s [%(run_id)s] %(name)s: %(message)s")
    formatter.converter = time.gmtime

    app_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)
    app_handler.addFilter(run_filter)

    err_handler = RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(formatter)
    err_handler.addFilter(run_filter)

    root.addHandler(app_handler)
    root.addHandler(err_handler)
