"""
Alembic env: подключение к PostgreSQL из переменных окружения.

Используются WP_DATABASE_URL или DATABASE_URL; при отсутствии — значение из alembic.ini.
Загружается .env из корня проекта.
"""

from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Корень проекта для загрузки .env и sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Загрузка .env (DATABASE_URL, WP_DATABASE_URL).
# Сначала UTF-8; при ошибке декодирования — cp1251 (Windows).
try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env", encoding="utf-8")
except Exception:
    try:
        load_dotenv(_project_root / ".env", encoding="cp1251")
    except Exception:
        pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL из окружения (приоритет) или из alembic.ini
database_url = os.environ.get("WP_DATABASE_URL") or os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
