#!/usr/bin/env python3
"""
Unit-тесты WP Fetcher (Этап 3): пагинация, X-WP-TotalPages, fallback, параметры, маппинг.

Запуск из корня проекта:
  python tests/test_wp_fetcher.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wp.fetcher import (
    _total_pages,
    fetch_categories,
    fetch_posts,
    fetch_pages,
    fetch_users,
)
from wp.mapper import post_to_content, content_embedded_terms


def test_total_pages_from_header() -> bool:
    """Корректная остановка по X-WP-TotalPages."""
    assert _total_pages({"X-WP-TotalPages": "3"}) == 3
    assert _total_pages({"x-wp-totalpages": "5"}) == 5
    assert _total_pages({}) == 1
    assert _total_pages(None) == 1
    return True


def test_total_pages_fallback_invalid() -> bool:
    """Fallback при отсутствии/битом X-WP-TotalPages: не падать, возвращать >= 1."""
    assert _total_pages({"X-WP-TotalPages": "bad"}) == 1
    assert _total_pages({"X-WP-TotalPages": ""}) == 1
    assert _total_pages({"X-WP-TotalPages": "0"}) == 1
    assert _total_pages({"X-WP-TotalPages": "-1"}) == 1
    return True


def test_fetch_users_pagination_two_pages() -> bool:
    """Пагинация на 2+ страницах: мок get_with_headers."""
    client = MagicMock()
    client.get_with_headers.side_effect = [
        ([{"id": i, "slug": f"u{i}", "name": f"User {i}"} for i in range(100)], {"X-WP-TotalPages": "2"}),
        ([{"id": 100 + i, "slug": f"u{100+i}", "name": f"User {100+i}"} for i in range(30)], {"X-WP-TotalPages": "2"}),
    ]
    result = fetch_users(client, "main", per_page=100, run_id="r1")
    assert len(result) == 130
    assert result[0].wp_user_id == 0 and result[0].slug == "u0"
    assert result[99].wp_user_id == 99
    assert result[100].wp_user_id == 100
    assert client.get_with_headers.call_count == 2
    client.get_with_headers.assert_any_call("/users", params={"per_page": 100, "page": 1}, run_id="r1")
    client.get_with_headers.assert_any_call("/users", params={"per_page": 100, "page": 2}, run_id="r1")
    return True


def test_fetch_users_stop_on_empty_page() -> bool:
    """Fallback: остановка при пустой странице (len < per_page)."""
    client = MagicMock()
    client.get_with_headers.return_value = (
        [{"id": 1, "slug": "a", "name": "A"}],
        {},
    )
    result = fetch_users(client, "main", per_page=100)
    assert len(result) == 1
    client.get_with_headers.assert_called_once()
    return True


def test_fetch_posts_params_status_and_embed() -> bool:
    """Для posts передаются status=publish и _embed."""
    client = MagicMock()
    client.get_with_headers.return_value = ([], {"X-WP-TotalPages": "1"})
    fetch_posts(client, "main", per_page=100, run_id="r1")
    client.get_with_headers.assert_called_once_with(
        "/posts",
        params={"status": "publish", "per_page": 100, "page": 1, "_embed": ""},
        run_id="r1",
    )
    return True


def test_fetch_pages_params_status_and_embed() -> bool:
    """Для pages передаются status=publish и _embed."""
    client = MagicMock()
    client.get_with_headers.return_value = ([], {"X-WP-TotalPages": "1"})
    fetch_pages(client, "main", per_page=100)
    client.get_with_headers.assert_called_once_with(
        "/pages",
        params={"status": "publish", "per_page": 100, "page": 1, "_embed": ""},
        run_id=None,
    )
    return True


def test_mapping_post_content_rendered() -> bool:
    """Маппинг: post_content только из content.rendered."""
    raw = {
        "id": 42,
        "title": {"rendered": "Title"},
        "slug": "hello",
        "content": {"rendered": "<p>Rendered content</p>", "raw": "Raw content"},
        "excerpt": {"rendered": ""},
        "status": "publish",
        "author": 1,
        "date_gmt": "2026-01-15T10:00:00",
        "modified_gmt": "2026-01-16T12:00:00",
    }
    row = post_to_content("main", raw)
    assert row.post_content == "<p>Rendered content</p>"
    assert row.wp_id == 42
    assert row.slug == "hello"
    assert row.author_id == 1
    assert row.published_at is not None
    return True


def test_mapping_embedded_terms() -> bool:
    """Извлечение slug, author_id, date, terms из _embedded."""
    raw = {
        "id": 10,
        "slug": "my-post",
        "author": 2,
        "date_gmt": "2026-02-01T08:00:00",
        "_embedded": {
            "wp:term": [
                [{"id": 1, "slug": "cat1", "name": "Category 1"}],
                [{"id": 5, "slug": "tag1", "name": "Tag 1"}, {"id": 6, "slug": "tag2", "name": "Tag 2"}],
            ]
        },
    }
    terms = content_embedded_terms("main", "post", 10, raw)
    assert len(terms) == 3
    by_tax = {}
    for t in terms:
        by_tax.setdefault(t.taxonomy, []).append(t.wp_term_id)
    assert by_tax["category"] == [1]
    assert sorted(by_tax["post_tag"]) == [5, 6]
    row = post_to_content("main", {**raw, "title": {"rendered": "T"}, "content": {"rendered": ""}, "excerpt": {"rendered": ""}, "status": "publish", "modified_gmt": raw["date_gmt"]})
    assert row.slug == "my-post"
    assert row.author_id == 2
    assert row.published_at is not None
    return True


def test_fetch_non_list_safe_finish() -> bool:
    """Если API вернул не список — лог и безопасное завершение без traceback."""
    client = MagicMock()
    client.get_with_headers.return_value = ({"error": "object"}, {"X-WP-TotalPages": "1"})
    result = fetch_users(client, "main", per_page=100)
    assert result == []
    client.get_with_headers.assert_called_once()
    return True


def test_fetch_categories_pagination() -> bool:
    """fetch_categories: две страницы, без дубликатов."""
    client = MagicMock()
    client.get_with_headers.side_effect = [
        ([{"id": i, "name": f"C{i}", "slug": f"c{i}", "parent": 0} for i in range(100)], {"X-WP-TotalPages": "2"}),
        ([{"id": 100 + i, "name": f"C{100+i}", "slug": f"c{100+i}", "parent": 0} for i in range(20)], {"X-WP-TotalPages": "2"}),
    ]
    result = fetch_categories(client, "main", per_page=100)
    assert len(result) == 120
    ids = [r.wp_term_id for r in result]
    assert len(ids) == len(set(ids))
    return True


def run_all() -> bool:
    cases = [
        ("_total_pages from header", test_total_pages_from_header),
        ("_total_pages fallback invalid", test_total_pages_fallback_invalid),
        ("fetch_users pagination 2 pages", test_fetch_users_pagination_two_pages),
        ("fetch_users stop on empty page", test_fetch_users_stop_on_empty_page),
        ("fetch_posts params status _embed", test_fetch_posts_params_status_and_embed),
        ("fetch_pages params status _embed", test_fetch_pages_params_status_and_embed),
        ("mapping post_content rendered", test_mapping_post_content_rendered),
        ("mapping embedded terms", test_mapping_embedded_terms),
        ("fetch non-list safe finish", test_fetch_non_list_safe_finish),
        ("fetch_categories pagination", test_fetch_categories_pagination),
    ]
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


if __name__ == "__main__":
    print("WP fetcher (stage 3) unit tests")
    sys.exit(0 if run_all() else 1)
