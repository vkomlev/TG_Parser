#!/usr/bin/env python3
"""
Smoke/unit-тесты WordPress Source (Этап 1 MVP, Шаг 7 — тестовый контур).

- Unit: маппинг API → модель, валидация конфига, расчёт паузы/retry.
- Integration: полный sync — через tests/test_wp_storage.py --integration (БД) или ручной прогон wp_sync_skill.py sync --site <id>.

Полный контур: test_wp_client, test_wp_fetcher, test_wp_output, test_wp_storage, test_wp_cli, smoke_wp --unit-only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wp.client import WPRestClient, _backoff_delay, _should_retry
from wp.config import load_config, load_sites_list
from wp.mapper import (
    category_to_term,
    content_embedded_terms,
    page_to_content,
    post_to_content,
    tag_to_term,
    user_to_author,
)


def test_mapper_user_to_author() -> bool:
    raw = {"id": 1, "slug": "admin", "name": "Admin", "username": "admin"}
    row = user_to_author("main", raw)
    assert row.site_id == "main"
    assert row.wp_user_id == 1
    assert row.login == "admin"
    assert row.slug == "admin"
    assert row.name == "Admin"
    return True


def test_mapper_category_to_term() -> bool:
    raw = {"id": 5, "name": "News", "slug": "news", "parent": 0}
    row = category_to_term("main", raw)
    assert row.site_id == "main"
    assert row.taxonomy == "category"
    assert row.wp_term_id == 5
    assert row.slug == "news"
    assert row.parent_id is None
    return True


def test_mapper_tag_to_term() -> bool:
    raw = {"id": 10, "name": "python", "slug": "python", "parent": 0}
    row = tag_to_term("main", raw)
    assert row.taxonomy == "post_tag"
    assert row.wp_term_id == 10
    return True


def test_mapper_post_to_content() -> bool:
    raw = {
        "id": 42,
        "title": {"rendered": "Hello World"},
        "slug": "hello-world",
        "content": {"rendered": "<p>Content.</p>"},
        "excerpt": {"rendered": ""},
        "status": "publish",
        "author": 1,
        "date_gmt": "2026-01-01T10:00:00",
        "modified_gmt": "2026-02-20T14:00:00",
    }
    row = post_to_content("main", raw)
    assert row.content_type == "post"
    assert row.wp_id == 42
    assert row.title == "Hello World"
    assert row.slug == "hello-world"
    assert row.post_content == "<p>Content.</p>"
    assert row.status == "publish"
    assert row.author_id == 1
    return True


def test_mapper_content_embedded_terms() -> bool:
    raw = {
        "id": 42,
        "_embedded": {
            "wp:term": [
                [{"id": 1, "slug": "news", "name": "News"}],
                [{"id": 2, "slug": "python", "name": "python"}],
            ]
        },
    }
    rows = content_embedded_terms("main", "post", 42, raw)
    assert len(rows) == 2
    assert rows[0].taxonomy == "category" and rows[0].wp_term_id == 1
    assert rows[1].taxonomy == "post_tag" and rows[1].wp_term_id == 2
    return True


def test_config_validation_missing_site_id() -> bool:
    """Отсутствие site_id в конфиге — ошибка."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("sites:\n  - base_url: https://x.com\n")
        path = Path(f.name)
    try:
        with patch.dict(os.environ, {}, clear=False):
            for k in list(os.environ):
                if k.startswith("WP_SITE_"):
                    del os.environ[k]
        try:
            load_config(config_path=path, project_root=PROJECT_ROOT)
            return False
        except ValueError as e:
            assert "site_id" in str(e).lower() or "base_url" in str(e).lower()
            return True
    finally:
        path.unlink(missing_ok=True)


def test_config_validation_missing_creds() -> bool:
    """Отсутствие кредов в env для сайта — ошибка."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("sites:\n  - site_id: main\n    base_url: https://example.com\n")
        path = Path(f.name)
    try:
        with patch.dict(os.environ, {}, clear=False):
            for k in list(os.environ):
                if k.startswith("WP_SITE_"):
                    del os.environ[k]
        try:
            load_config(config_path=path, project_root=PROJECT_ROOT)
            return False
        except ValueError as e:
            assert "WP_SITE" in str(e) or "APP_PASSWORD" in str(e) or "переменные" in str(e).lower()
            return True
    finally:
        path.unlink(missing_ok=True)


def test_load_sites_list_valid_yaml() -> bool:
    """list-sites: загрузка списка сайтов из валидного YAML (fixture, не боевой config)."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: fixture\n    base_url: https://example.com\n    name: Fixture\n")
        path = Path(f.name)
    try:
        sites = load_sites_list(path)
        assert isinstance(sites, list)
        assert len(sites) == 1
        assert (sites[0].get("site_id") or "").strip() == "fixture"
        return True
    finally:
        path.unlink(missing_ok=True)


def test_load_sites_yaml_invalid_raises_value_error() -> bool:
    """Битый YAML приводит к ValueError, не к сырому YAMLError/traceback."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: x\n  bad: indent\n")
        path = Path(f.name)
    try:
        try:
            load_sites_list(path)
            return False
        except ValueError as e:
            assert "YAML" in str(e) or "разбора" in str(e)
            return True
    finally:
        path.unlink(missing_ok=True)


def test_backoff_delay() -> bool:
    """Пауза между запросами: при 3 req/s не менее 1/3 с."""
    from wp.client import MIN_DELAY_BETWEEN_REQUESTS
    assert MIN_DELAY_BETWEEN_REQUESTS <= (1.0 / 3.0) + 0.01
    d = _backoff_delay(0, None)
    assert d >= 1.0
    d429 = _backoff_delay(0, 5)
    assert d429 == 5.0
    return True


def test_should_retry() -> bool:
    assert _should_retry(429, None) is True
    assert _should_retry(500, None) is True
    assert _should_retry(401, None) is False
    assert _should_retry(403, None) is False
    assert _should_retry(404, None) is False
    assert _should_retry(400, None) is False
    assert _should_retry(None, Exception()) is True
    return True


def run_unit_tests() -> bool:
    cases = [
        ("mapper user_to_author", test_mapper_user_to_author),
        ("mapper category_to_term", test_mapper_category_to_term),
        ("mapper tag_to_term", test_mapper_tag_to_term),
        ("mapper post_to_content", test_mapper_post_to_content),
        ("mapper content_embedded_terms", test_mapper_content_embedded_terms),
        ("config validation missing site_id", test_config_validation_missing_site_id),
        ("config validation missing creds", test_config_validation_missing_creds),
        ("load_sites_list", test_load_sites_list_valid_yaml),
        ("load_sites_yaml invalid -> ValueError", test_load_sites_yaml_invalid_raises_value_error),
        ("backoff_delay", test_backoff_delay),
        ("should_retry", test_should_retry),
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit-only", action="store_true", help="Только unit-тесты")
    ap.add_argument("--integration", action="store_true", help="Запустить интеграционный sync (нужны WP_DATABASE_URL и креды)")
    args = ap.parse_args()

    print("WP smoke/unit tests")
    if not run_unit_tests():
        return 1
    if args.unit_only:
        print("Unit tests passed.")
        return 0
    if args.integration:
        print("Integration: run manually with real DB and WP site.")
        return 0
    print("Unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
