"""Сохранение данных WP: PostgreSQL или SQLite (fallback). Единый контракт операций."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Union

from .mapper import AuthorRow, ContentRow, ContentTermRow, TermRow

logger = logging.getLogger("wp.storage")

STORAGE_BACKEND_ENV = "WP_STORAGE_BACKEND"
STORAGE_FALLBACK_ENV = "WP_STORAGE_FALLBACK"  # auto | off (по умолчанию off — fail fast при недоступности Postgres)
DATABASE_URL_ENV = "WP_DATABASE_URL"


def _pg_connect():
    import psycopg2
    return psycopg2.connect(get_connection_string())


def _pg_json(val):
    import psycopg2.extras
    return psycopg2.extras.Json(val) if val is not None else None


def _resolve_backend() -> str:
    backend = (os.environ.get(STORAGE_BACKEND_ENV) or "").strip().lower()
    if backend == "sqlite":
        return "sqlite"
    url = (os.environ.get(DATABASE_URL_ENV) or os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise ValueError(
            "Задайте WP_DATABASE_URL для PostgreSQL или явно укажите WP_STORAGE_BACKEND=sqlite."
        )
    try:
        conn = _pg_connect()
        conn.close()
        return "postgres"
    except Exception as e:
        fallback = (os.environ.get(STORAGE_FALLBACK_ENV) or "off").strip().lower()
        if fallback == "auto":
            logger.warning("PostgreSQL недоступен (%s), переключаемся на SQLite (WP_STORAGE_FALLBACK=auto)", e)
            return "sqlite"
        logger.error("PostgreSQL недоступен (%s). Для авто-перехода на SQLite задайте WP_STORAGE_FALLBACK=auto", e)
        raise


_backend: Optional[str] = None
_sqlite = None


def _get_backend() -> str:
    global _backend, _sqlite
    if _backend is None:
        _backend = _resolve_backend()
        if _backend == "sqlite":
            from . import storage_sqlite as _sqlite_mod  # noqa: F401
            _sqlite = _sqlite_mod
        else:
            _sqlite = None
    return _backend


def _get_sqlite():
    _get_backend()
    return _sqlite


def get_connection_string() -> str:
    url = os.environ.get(DATABASE_URL_ENV) or os.environ.get("DATABASE_URL") or ""
    if not url.strip():
        raise ValueError(
            f"Задайте {DATABASE_URL_ENV} или DATABASE_URL для подключения к PostgreSQL."
        )
    return url.strip()


@contextmanager
def get_connection() -> Iterator[Union[object, sqlite3.Connection]]:
    if _get_backend() == "sqlite":
        project_root = Path(__file__).resolve().parent.parent
        with _get_sqlite().get_connection(project_root=project_root) as conn:
            yield conn
    else:
        conn = _pg_connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _ts(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def upsert_site(
    conn: Union[object, sqlite3.Connection],
    site_id: str,
    base_url: str,
    name: Optional[str],
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().upsert_site(conn, site_id, base_url, name)
    logger.debug("upsert_site site_id=%s", site_id, extra={"site_id": site_id})
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wp_sites (site_id, base_url, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (site_id) DO UPDATE SET
                base_url = EXCLUDED.base_url,
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
            """,
            (site_id, base_url, name or None, now, now),
        )


def upsert_authors(
    conn: Union[object, sqlite3.Connection],
    rows: List[AuthorRow],
    synced_at: datetime,
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().upsert_authors(conn, rows, synced_at)
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_authors site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO wp_authors (site_id, wp_user_id, login, name, slug, raw_json, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (site_id, wp_user_id) DO UPDATE SET
                    login = EXCLUDED.login,
                    name = EXCLUDED.name,
                    slug = EXCLUDED.slug,
                    raw_json = EXCLUDED.raw_json,
                    synced_at = EXCLUDED.synced_at
                """,
                (
                    r.site_id,
                    r.wp_user_id,
                    r.login,
                    r.name,
                    r.slug,
                    _pg_json(r.raw_json),
                    synced_at,
                ),
            )


def upsert_terms(
    conn: Union[object, sqlite3.Connection],
    rows: List[TermRow],
    synced_at: datetime,
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().upsert_terms(conn, rows, synced_at)
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_terms site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO wp_terms (site_id, taxonomy, wp_term_id, name, slug, parent_id, raw_json, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (site_id, taxonomy, wp_term_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    slug = EXCLUDED.slug,
                    parent_id = EXCLUDED.parent_id,
                    raw_json = EXCLUDED.raw_json,
                    synced_at = EXCLUDED.synced_at
                """,
                (
                    r.site_id,
                    r.taxonomy,
                    r.wp_term_id,
                    r.name,
                    r.slug,
                    r.parent_id,
                    _pg_json(r.raw_json),
                    synced_at,
                ),
            )


def upsert_content(
    conn: Union[object, sqlite3.Connection],
    rows: List[ContentRow],
    synced_at: datetime,
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().upsert_content(conn, rows, synced_at)
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_content site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO wp_content (
                    site_id, content_type, wp_id, title, slug, post_content, excerpt,
                    status, author_id, published_at, modified_at,
                    seo_title, seo_description, seo_json, raw_json, synced_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (site_id, content_type, wp_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    slug = EXCLUDED.slug,
                    post_content = EXCLUDED.post_content,
                    excerpt = EXCLUDED.excerpt,
                    status = EXCLUDED.status,
                    author_id = EXCLUDED.author_id,
                    published_at = EXCLUDED.published_at,
                    modified_at = EXCLUDED.modified_at,
                    seo_title = EXCLUDED.seo_title,
                    seo_description = EXCLUDED.seo_description,
                    seo_json = EXCLUDED.seo_json,
                    raw_json = EXCLUDED.raw_json,
                    synced_at = EXCLUDED.synced_at
                """,
                (
                    r.site_id,
                    r.content_type,
                    r.wp_id,
                    r.title,
                    r.slug,
                    r.post_content,
                    r.excerpt,
                    r.status,
                    r.author_id,
                    _ts(r.published_at),
                    _ts(r.modified_at),
                    r.seo_title,
                    r.seo_description,
                    _pg_json(r.seo_json),
                    _pg_json(r.raw_json),
                    synced_at,
                ),
            )


def upsert_content_terms(
    conn: Union[object, sqlite3.Connection],
    rows: List[ContentTermRow],
    synced_at: datetime,
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().upsert_content_terms(conn, rows, synced_at)
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_content_terms site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO wp_content_terms (site_id, content_type, wp_content_id, taxonomy, wp_term_id, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (site_id, content_type, wp_content_id, taxonomy, wp_term_id) DO UPDATE SET
                    synced_at = EXCLUDED.synced_at
                """,
                (r.site_id, r.content_type, r.wp_content_id, r.taxonomy, r.wp_term_id, synced_at),
            )


def insert_sync_run(
    conn: Union[object, sqlite3.Connection],
    run_id: str,
    site_id: str,
    started_at: datetime,
) -> None:
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().insert_sync_run(conn, run_id, site_id, started_at)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO wp_sync_runs (run_id, site_id, started_at, status)
            VALUES (%s, %s, %s, 'running')
            """,
            (run_id, site_id, _ts(started_at) if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)),
        )


def update_sync_run(
    conn: Union[object, sqlite3.Connection],
    run_id: str,
    site_id: str,
    finished_at: datetime,
    status: str,
    error_code: Optional[str],
    posts_count: int,
    pages_count: int,
    terms_count: int,
    authors_count: int,
) -> int:
    """Обновить запись run. Возвращает rowcount (ожидается 1)."""
    if isinstance(conn, sqlite3.Connection):
        return _get_sqlite().update_sync_run(
            conn, run_id, site_id, finished_at, status, error_code,
            posts_count, pages_count, terms_count, authors_count,
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE wp_sync_runs
            SET finished_at = %s, status = %s, error_code = %s,
                posts_count = %s, pages_count = %s, terms_count = %s, authors_count = %s
            WHERE run_id = %s AND site_id = %s
            """,
            (
                finished_at if finished_at.tzinfo else finished_at.replace(tzinfo=timezone.utc),
                status,
                error_code,
                posts_count,
                pages_count,
                terms_count,
                authors_count,
                run_id,
                site_id,
            ),
        )
        return cur.rowcount
