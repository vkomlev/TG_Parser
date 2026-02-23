"""SQLite backend для WP storage: те же операции, DDL в migrations/wp/sqlite/."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from .mapper import AuthorRow, ContentRow, ContentTermRow, TermRow

logger = logging.getLogger("wp.storage.sqlite")

STORAGE_PATH_ENV = "WP_STORAGE_PATH"
SQLITE_DEFAULT_NAME = "wp_sync.db"


def get_sqlite_path(project_root: Optional[Path] = None) -> Path:
    path = os.environ.get(STORAGE_PATH_ENV, "").strip()
    if path:
        return Path(path)
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / SQLITE_DEFAULT_NAME


@contextmanager
def get_connection(project_root: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    path = get_sqlite_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='wp_sites'"
    )
    if cur.fetchone():
        return
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations" / "wp" / "sqlite"
    for name in sorted(migrations_dir.glob("*.sql")):
        sql = name.read_text(encoding="utf-8").strip()
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            # Убрать ведущие строки-комментарии
            while stmt and stmt.split("\n")[0].strip().startswith("--"):
                stmt = "\n".join(stmt.split("\n")[1:]).strip()
            if stmt and not stmt.startswith("--"):
                conn.execute(stmt)


def _ts(d: Optional[datetime]) -> Optional[str]:
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.isoformat()


def _json_val(obj) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def upsert_site(
    conn: sqlite3.Connection,
    site_id: str,
    base_url: str,
    name: Optional[str],
) -> None:
    logger.debug("upsert_site site_id=%s", site_id, extra={"site_id": site_id})
    now = _ts(datetime.now(timezone.utc))
    conn.execute(
        """
        INSERT INTO wp_sites (site_id, base_url, name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (site_id) DO UPDATE SET
            base_url = excluded.base_url,
            name = excluded.name,
            updated_at = excluded.updated_at
        """,
        (site_id, base_url, name or None, now, now),
    )


def upsert_authors(
    conn: sqlite3.Connection,
    rows: List[AuthorRow],
    synced_at: datetime,
) -> None:
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_authors site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    synced = _ts(synced_at)
    for r in rows:
        conn.execute(
            """
            INSERT INTO wp_authors (site_id, wp_user_id, login, name, slug, raw_json, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (site_id, wp_user_id) DO UPDATE SET
                login = excluded.login, name = excluded.name, slug = excluded.slug,
                raw_json = excluded.raw_json, synced_at = excluded.synced_at
            """,
            (r.site_id, r.wp_user_id, r.login, r.name, r.slug, _json_val(r.raw_json), synced),
        )


def upsert_terms(
    conn: sqlite3.Connection,
    rows: List[TermRow],
    synced_at: datetime,
) -> None:
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_terms site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    synced = _ts(synced_at)
    for r in rows:
        conn.execute(
            """
            INSERT INTO wp_terms (site_id, taxonomy, wp_term_id, name, slug, parent_id, raw_json, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (site_id, taxonomy, wp_term_id) DO UPDATE SET
                name = excluded.name, slug = excluded.slug, parent_id = excluded.parent_id,
                raw_json = excluded.raw_json, synced_at = excluded.synced_at
            """,
            (r.site_id, r.taxonomy, r.wp_term_id, r.name, r.slug, r.parent_id, _json_val(r.raw_json), synced),
        )


def upsert_content(
    conn: sqlite3.Connection,
    rows: List[ContentRow],
    synced_at: datetime,
) -> None:
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_content site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    synced = _ts(synced_at)
    for r in rows:
        conn.execute(
            """
            INSERT INTO wp_content (
                site_id, content_type, wp_id, title, slug, post_content, excerpt,
                status, author_id, published_at, modified_at,
                seo_title, seo_description, seo_json, raw_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (site_id, content_type, wp_id) DO UPDATE SET
                title = excluded.title, slug = excluded.slug, post_content = excluded.post_content,
                excerpt = excluded.excerpt, status = excluded.status, author_id = excluded.author_id,
                published_at = excluded.published_at, modified_at = excluded.modified_at,
                seo_title = excluded.seo_title, seo_description = excluded.seo_description,
                seo_json = excluded.seo_json, raw_json = excluded.raw_json, synced_at = excluded.synced_at
            """,
            (
                r.site_id, r.content_type, r.wp_id, r.title, r.slug, r.post_content, r.excerpt,
                r.status, r.author_id, _ts(r.published_at), _ts(r.modified_at),
                r.seo_title, r.seo_description, _json_val(r.seo_json), _json_val(r.raw_json), synced,
            ),
        )


def upsert_content_terms(
    conn: sqlite3.Connection,
    rows: List[ContentTermRow],
    synced_at: datetime,
) -> None:
    if not rows:
        return
    site_id = rows[0].site_id if rows else ""
    logger.debug("upsert_content_terms site_id=%s count=%s", site_id, len(rows), extra={"site_id": site_id})
    synced = _ts(synced_at)
    for r in rows:
        conn.execute(
            """
            INSERT INTO wp_content_terms (site_id, content_type, wp_content_id, taxonomy, wp_term_id, synced_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (site_id, content_type, wp_content_id, taxonomy, wp_term_id) DO UPDATE SET
                synced_at = excluded.synced_at
            """,
            (r.site_id, r.content_type, r.wp_content_id, r.taxonomy, r.wp_term_id, synced),
        )


def insert_sync_run(
    conn: sqlite3.Connection,
    run_id: str,
    site_id: str,
    started_at: datetime,
) -> None:
    conn.execute(
        "INSERT INTO wp_sync_runs (run_id, site_id, started_at, status) VALUES (?, ?, ?, 'running')",
        (run_id, site_id, _ts(started_at)),
    )


def update_sync_run(
    conn: sqlite3.Connection,
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
    cur = conn.execute(
        """
        UPDATE wp_sync_runs
        SET finished_at = ?, status = ?, error_code = ?,
            posts_count = ?, pages_count = ?, terms_count = ?, authors_count = ?
        WHERE run_id = ? AND site_id = ?
        """,
        (_ts(finished_at), status, error_code, posts_count, pages_count, terms_count, authors_count, run_id, site_id),
    )
    return cur.rowcount
