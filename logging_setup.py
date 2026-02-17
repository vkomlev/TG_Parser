"""Настройка логирования приложения.

Логи пишутся в папку `logs/` рядом с файлом и ротируются по размеру.
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_app_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    """Настроить логирование в `logs/app.log` с ротацией.

    Args:
        logs_dir: Каталог для логов.
        level: Уровень логирования (по умолчанию INFO).

    Returns:
        None.
    """

    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Идемпотентность: не добавляем хендлеры повторно.
    for h in root.handlers:
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "").endswith("app.log"):
            return

    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s")
    # UTC timestamps, как в JSON-экспорте
    formatter.converter = time.gmtime

    app_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)

    err_handler = RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(formatter)

    root.addHandler(app_handler)
    root.addHandler(err_handler)
