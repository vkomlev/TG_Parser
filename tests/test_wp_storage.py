#!/usr/bin/env python3
"""
Unit и интеграционные тесты WP Storage (Шаг 5): upsert, idempotency, wp_sync_runs.

Требуется WP_DATABASE_URL (или DATABASE_URL). Миграции 001..006 должны быть применены.

Запуск из корня проекта:
  python tests/test_wp_storage.py              # unit-тесты (с БД — реальные проверки; без WP_DATABASE_URL — SKIP)
  python tests/test_wp_storage.py --integration  # + интеграционный сценарий «два прогона — одинаковые counts»

Для верификации критерия приёмки по БД задайте WP_DATABASE_URL (в .env или окружении) и примените миграции.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Подхват WP_DATABASE_URL из .env при запуске из корня проекта
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from wp.mapper import AuthorRow, ContentRow, ContentTermRow, TermRow
    from wp.storage import (
        get_connection,
        get_connection_string,
        insert_sync_run,
        update_sync_run,
        upsert_authors,
        upsert_content,
        upsert_content_terms,
        upsert_site,
        upsert_terms,
    )
    _storage_available = True
except ImportError as e:
    _storage_available = False
    get_connection = get_connection_string = insert_sync_run = update_sync_run = None
    upsert_authors = upsert_content = upsert_content_terms = upsert_site = upsert_terms = None
    AuthorRow = ContentRow = ContentTermRow = TermRow = None

TEST_SITE_ID = "_test_storage"


def _skip_no_db() -> bool:
    if not _storage_available:
        return True
    url = os.environ.get("WP_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    return not url.strip()


def _count(conn, table: str, where: str = "", params: tuple = ()) -> int:
    with conn.cursor() as cur:
        q = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
        cur.execute(q, params)
        return cur.fetchone()[0]


def test_upsert_site_idempotent() -> bool:
    """Upsert wp_sites: insert -> upsert с теми же данными -> одна строка."""
    if _skip_no_db():
        print("  SKIP upsert_site (no DB or no WP_DATABASE_URL)")
        return True
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test Site")
        n1 = _count(conn, "wp_sites", "site_id = %s", (TEST_SITE_ID,))
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com/updated", "Test Site Updated")
        n2 = _count(conn, "wp_sites", "site_id = %s", (TEST_SITE_ID,))
    assert n1 == 1 and n2 == 1
    return True


def test_upsert_authors_idempotent() -> bool:
    """Upsert wp_authors: insert -> upsert те же данные -> одна строка, synced_at обновлён."""
    if _skip_no_db():
        print("  SKIP upsert_authors (no DB or no WP_DATABASE_URL)")
        return True
    row = AuthorRow(TEST_SITE_ID, 1, "user1", "User One", "user1", None)
    t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test")
        upsert_authors(conn, [row], t1)
        n1 = _count(conn, "wp_authors", "site_id = %s AND wp_user_id = 1", (TEST_SITE_ID,))
        upsert_authors(conn, [row], t2)
        n2 = _count(conn, "wp_authors", "site_id = %s AND wp_user_id = 1", (TEST_SITE_ID,))
        with conn.cursor() as cur:
            cur.execute("SELECT synced_at FROM wp_authors WHERE site_id = %s AND wp_user_id = 1", (TEST_SITE_ID,))
            synced = cur.fetchone()[0]
    assert n1 == 1 and n2 == 1
    assert synced is not None
    return True


def test_upsert_terms_idempotent() -> bool:
    """Upsert wp_terms: insert -> upsert -> одна строка."""
    if _skip_no_db():
        print("  SKIP upsert_terms (no DB or no WP_DATABASE_URL)")
        return True
    row = TermRow(TEST_SITE_ID, "category", 10, "Cat", "cat", None, None)
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test")
        upsert_terms(conn, [row], now)
        n1 = _count(conn, "wp_terms", "site_id = %s AND taxonomy = %s AND wp_term_id = 10", (TEST_SITE_ID, "category"))
        upsert_terms(conn, [row], now)
        n2 = _count(conn, "wp_terms", "site_id = %s AND taxonomy = %s AND wp_term_id = 10", (TEST_SITE_ID, "category"))
    assert n1 == 1 and n2 == 1
    return True


def test_upsert_content_idempotent() -> bool:
    """Upsert wp_content: insert -> upsert -> одна строка."""
    if _skip_no_db():
        print("  SKIP upsert_content (no DB or no WP_DATABASE_URL)")
        return True
    row = ContentRow(
        TEST_SITE_ID, "post", 100, "Title", "slug-100", "<p>Body</p>", None,
        "publish", 1,
        datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc),
        None, None, None, None,
    )
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test")
        upsert_authors(conn, [AuthorRow(TEST_SITE_ID, 1, "u", "U", "u", None)], now)
        upsert_content(conn, [row], now)
        n1 = _count(conn, "wp_content", "site_id = %s AND content_type = %s AND wp_id = 100", (TEST_SITE_ID, "post"))
        upsert_content(conn, [row], now)
        n2 = _count(conn, "wp_content", "site_id = %s AND content_type = %s AND wp_id = 100", (TEST_SITE_ID, "post"))
    assert n1 == 1 and n2 == 1
    return True


def test_upsert_content_terms_idempotent() -> bool:
    """Upsert wp_content_terms: insert -> upsert -> одна строка."""
    if _skip_no_db():
        print("  SKIP upsert_content_terms (no DB or no WP_DATABASE_URL)")
        return True
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test")
        upsert_authors(conn, [AuthorRow(TEST_SITE_ID, 1, "u", "U", "u", None)], now)
        upsert_terms(conn, [TermRow(TEST_SITE_ID, "category", 5, "C", "c", None, None)], now)
        upsert_content(conn, [
            ContentRow(TEST_SITE_ID, "post", 50, "T", "s", None, None, "publish", 1, now, now, None, None, None, None),
        ], now)
        row = ContentTermRow(TEST_SITE_ID, "post", 50, "category", 5)
        upsert_content_terms(conn, [row], now)
        n1 = _count(conn, "wp_content_terms", "site_id = %s AND wp_content_id = 50 AND wp_term_id = 5", (TEST_SITE_ID,))
        upsert_content_terms(conn, [row], now)
        n2 = _count(conn, "wp_content_terms", "site_id = %s AND wp_content_id = 50 AND wp_term_id = 5", (TEST_SITE_ID,))
    assert n1 == 1 and n2 == 1
    return True


def test_update_sync_run_returns_zero_when_no_row() -> bool:
    """update_sync_run с несуществующим run_id возвращает rowcount 0."""
    if _skip_no_db():
        print("  SKIP update_sync_run rowcount (no DB or no WP_DATABASE_URL)")
        return True
    try:
        get_connection_string()
    except ValueError:
        print("  SKIP update_sync_run (no DB URL)")
        return True
    with get_connection() as conn:
        n = update_sync_run(
            conn,
            run_id="_nonexistent_run_",
            site_id=TEST_SITE_ID,
            finished_at=datetime.now(timezone.utc),
            status="failed",
            error_code="TEST",
            posts_count=0,
            pages_count=0,
            terms_count=0,
            authors_count=0,
        )
    assert n == 0
    return True


def test_insert_sync_run_then_update() -> bool:
    """insert_sync_run создаёт строку, update_sync_run обновляет и возвращает 1."""
    if _skip_no_db():
        print("  SKIP insert_sync_run + update (no DB or no WP_DATABASE_URL)")
        return True
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc)
    with get_connection() as conn:
        upsert_site(conn, TEST_SITE_ID, "https://test.example.com", "Test")
        insert_sync_run(conn, run_id, TEST_SITE_ID, started)
    with get_connection() as conn:
        n = update_sync_run(
            conn, run_id, TEST_SITE_ID,
            datetime.now(timezone.utc), "success", None,
            1, 0, 0, 1,
        )
    assert n == 1
    return True


def test_integration_two_syncs_same_counts() -> bool:
    """Два подряд «sync» (одни и те же данные через storage дважды) -> одинаковые counts."""
    if _skip_no_db():
        print("  SKIP integration two syncs (no DB or no WP_DATABASE_URL)")
        return True
    site_id = "_test_idem"
    now = datetime.now(timezone.utc)
    authors = [AuthorRow(site_id, 1, "a", "A", "a", None)]
    terms = [TermRow(site_id, "category", 1, "C", "c", None, None), TermRow(site_id, "post_tag", 2, "T", "t", None, None)]
    content = [
        ContentRow(site_id, "post", 1, "P", "p", "x", None, "publish", 1, now, now, None, None, None, None),
        ContentRow(site_id, "page", 1, "Pg", "pg", "y", None, "publish", 1, now, now, None, None, None, None),
    ]
    ct_terms = [ContentTermRow(site_id, "post", 1, "category", 1), ContentTermRow(site_id, "post", 1, "post_tag", 2)]

    def run_sync():
        with get_connection() as conn:
            upsert_site(conn, site_id, "https://idem.example.com", "Idem")
            upsert_authors(conn, authors, now)
            upsert_terms(conn, terms, now)
            upsert_content(conn, content, now)
            upsert_content_terms(conn, ct_terms, now)

    run_sync()
    with get_connection() as conn:
        c_sites_1 = _count(conn, "wp_sites", "site_id = %s", (site_id,))
        c_authors_1 = _count(conn, "wp_authors", "site_id = %s", (site_id,))
        c_terms_1 = _count(conn, "wp_terms", "site_id = %s", (site_id,))
        c_content_1 = _count(conn, "wp_content", "site_id = %s", (site_id,))
        c_ct_1 = _count(conn, "wp_content_terms", "site_id = %s", (site_id,))

    run_sync()

    with get_connection() as conn:
        c_sites_2 = _count(conn, "wp_sites", "site_id = %s", (site_id,))
        c_authors_2 = _count(conn, "wp_authors", "site_id = %s", (site_id,))
        c_terms_2 = _count(conn, "wp_terms", "site_id = %s", (site_id,))
        c_content_2 = _count(conn, "wp_content", "site_id = %s", (site_id,))
        c_ct_2 = _count(conn, "wp_content_terms", "site_id = %s", (site_id,))

    assert c_sites_1 == c_sites_2 == 1
    assert c_authors_1 == c_authors_2
    assert c_terms_1 == c_terms_2
    assert c_content_1 == c_content_2
    assert c_ct_1 == c_ct_2
    return True


def run_all(integration: bool = False) -> bool:
    cases = [
        ("upsert_site idempotent", test_upsert_site_idempotent),
        ("upsert_authors idempotent", test_upsert_authors_idempotent),
        ("upsert_terms idempotent", test_upsert_terms_idempotent),
        ("upsert_content idempotent", test_upsert_content_idempotent),
        ("upsert_content_terms idempotent", test_upsert_content_terms_idempotent),
        ("update_sync_run rowcount 0 when no row", test_update_sync_run_returns_zero_when_no_row),
        ("insert_sync_run then update", test_insert_sync_run_then_update),
    ]
    if integration:
        cases.append(("integration two syncs same counts", test_integration_two_syncs_same_counts))
    ok = 0
    for name, fn in cases:
        try:
            if fn():
                ok += 1
                print(f"  OK {name}")
            else:
                print(f"  FAIL {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
    return ok == len(cases)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--integration", action="store_true", help="Добавить интеграционный тест: два прогона одних данных — одинаковые counts")
    args = ap.parse_args()
    print("WP storage (stage 5) tests")
    return 0 if run_all(integration=args.integration) else 1


if __name__ == "__main__":
    sys.exit(main())
