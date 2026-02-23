#!/usr/bin/env python3
"""
Unit-тесты WP Output (Шаг 4): маппинг WP API -> модель -> JSON-контракт.

Запуск из корня проекта:
  python tests/test_wp_output.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wp.mapper import ContentRow, ContentTermRow, TermRow, post_to_content, content_embedded_terms
from wp.output import (
    build_content_export_list,
    build_multisite_aggregated,
    build_multi_site_output,
    build_single_site_output,
    content_row_to_export_dict,
    summary_to_export_dict,
    _terms_lookup,
)


def _row(site_id="main", content_type="post", wp_id=1, title="T", slug="s", post_content="<p>X</p>",
         excerpt=None, status="publish", author_id=1, published_at=None, modified_at=None,
         seo_title=None, seo_description=None, seo_json=None):
    return ContentRow(
        site_id=site_id,
        content_type=content_type,
        wp_id=wp_id,
        title=title,
        slug=slug,
        post_content=post_content,
        excerpt=excerpt,
        status=status,
        author_id=author_id,
        published_at=published_at or datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        modified_at=modified_at or datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        seo_title=seo_title,
        seo_description=seo_description,
        seo_json=seo_json,
        raw_json=None,
    )


def test_content_export_full() -> bool:
    """Полный набор полей контента в export-словаре."""
    row = _row(title="Hello", slug="hello-world", post_content="<p>Rendered</p>", excerpt="Short")
    ct = [ContentTermRow("main", "post", 1, "category", 5), ContentTermRow("main", "post", 1, "post_tag", 10)]
    terms = [TermRow("main", "category", 5, "News", "news", None, None), TermRow("main", "post_tag", 10, "python", "python", None, None)]
    lookup = _terms_lookup(terms)
    out = content_row_to_export_dict(row, ct, lookup)
    assert out["source"] == "wp"
    assert out["site_id"] == "main"
    assert out["content_type"] == "post"
    assert out["wp_id"] == 1
    assert out["slug"] == "hello-world"
    assert out["title"] == "Hello"
    assert out["post_content"] == "<p>Rendered</p>"
    assert out["excerpt"] == "Short"
    assert out["status"] == "publish"
    assert out["author_id"] == 1
    assert out["published_at"] is not None
    assert out["modified_at"] is not None
    assert "category" in out["taxonomies"] and "post_tag" in out["taxonomies"]
    assert len(out["taxonomies"]["category"]) == 1 and out["taxonomies"]["category"][0]["wp_term_id"] == 5
    assert len(out["taxonomies"]["post_tag"]) == 1 and out["taxonomies"]["post_tag"][0]["slug"] == "python"
    assert "seo" in out and "seo_title" in out["seo"]
    return True


def test_content_export_without_seo() -> bool:
    """Без SEO: seo_title, seo_description, yoast_head_json = null."""
    row = _row(seo_title=None, seo_description=None, seo_json=None)
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    assert out["seo"]["seo_title"] is None
    assert out["seo"]["seo_description"] is None
    assert out["seo"]["yoast_head_json"] is None
    return True


def test_content_export_with_seo() -> bool:
    """С SEO: yoast_head_json присутствует как объект."""
    yoast = {"title": "SEO Title", "og_description": "Desc"}
    row = _row(seo_title="SEO Title", seo_description="Desc", seo_json=yoast)
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    assert out["seo"]["seo_title"] == "SEO Title"
    assert out["seo"]["seo_description"] == "Desc"
    assert out["seo"]["yoast_head_json"] == yoast
    return True


def test_content_export_without_excerpt_content() -> bool:
    """Без excerpt и post_content: null в контракте."""
    row = _row(post_content=None, excerpt=None)
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    assert out["post_content"] is None
    assert out["excerpt"] is None
    return True


def test_content_export_empty_taxonomies() -> bool:
    """Нет связей с терминами: taxonomies category/post_tag — пустые списки."""
    row = _row()
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    assert out["taxonomies"]["category"] == []
    assert out["taxonomies"]["post_tag"] == []
    return True


def test_single_site_output_is_object() -> bool:
    """Single-site: один объект с run_id, site_id, status, content (массив)."""
    summary = {"run_id": "r1", "site_id": "main", "status": "success", "run_at": "2026-01-01T00:00:00", "error_code": None, "posts_count": 1, "pages_count": 0, "terms_count": 0, "authors_count": 1}
    content_export = [{"source": "wp", "wp_id": 1, "slug": "x"}]
    out = build_single_site_output(summary, content_export)
    assert isinstance(out, dict)
    assert out.get("run_id") == "r1"
    assert out.get("site_id") == "main"
    assert out.get("status") == "success"
    assert "content" in out and isinstance(out["content"], list)
    assert len(out["content"]) == 1
    return True


def test_multi_site_output_is_array() -> bool:
    """Multi-site: массив объектов."""
    one = build_single_site_output({"run_id": "r1", "site_id": "a", "status": "success", "run_at": "", "error_code": None, "posts_count": 0, "pages_count": 0, "terms_count": 0, "authors_count": 0}, [])
    two = build_single_site_output({"run_id": "r1", "site_id": "b", "status": "success", "run_at": "", "error_code": None, "posts_count": 0, "pages_count": 0, "terms_count": 0, "authors_count": 0}, [])
    out = build_multi_site_output([one, two])
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["site_id"] == "a" and out[1]["site_id"] == "b"
    return True


def test_multisite_aggregated_format() -> bool:
    """Агрегированный multi-site: один объект с run_id, status, totals, sites."""
    one = build_single_site_output({"run_id": "r1", "site_id": "a", "status": "success", "run_at": "", "error_code": None, "posts_count": 2, "pages_count": 1, "terms_count": 3, "authors_count": 1}, [])
    two = build_single_site_output({"run_id": "r1", "site_id": "b", "status": "failed", "run_at": "", "error_code": "AUTH", "posts_count": 0, "pages_count": 0, "terms_count": 0, "authors_count": 0}, [])
    out = build_multisite_aggregated("r1", 2, [one, two])  # exit 2 = partial
    assert isinstance(out, dict)
    assert out["run_id"] == "r1"
    assert out["status"] == "partial"
    assert "totals" in out
    assert out["totals"]["sites"] == 2
    assert out["totals"]["success"] == 1
    assert out["totals"]["failed"] == 1
    assert out["totals"]["posts_count"] == 2
    assert out["totals"]["pages_count"] == 1
    assert out["totals"]["terms_count"] == 3
    assert out["totals"]["authors_count"] == 1
    assert out["sites"] == [one, two]
    out_success = build_multisite_aggregated("r2", 0, [one, one])
    assert out_success["status"] == "success"
    out_failed = build_multisite_aggregated("r3", 1, [two, two])
    assert out_failed["status"] == "failed"
    return True


def test_required_keys_present() -> bool:
    """В документе контента есть обязательные ключи контракта."""
    row = _row()
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    required = ["source", "site_id", "content_type", "wp_id", "slug", "title", "post_content", "excerpt", "status", "author_id", "published_at", "modified_at", "taxonomies", "seo"]
    for k in required:
        assert k in out, k
    assert out["source"] == "wp"
    return True


def test_post_content_only_rendered() -> bool:
    """Цепочка WP API -> модель -> JSON: post_content только из content.rendered (нет content.raw)."""
    raw = {
        "id": 42,
        "title": {"rendered": "Title"},
        "slug": "hello",
        "content": {"rendered": "<p>Rendered only</p>", "raw": "Raw secret"},
        "excerpt": {"rendered": ""},
        "status": "publish",
        "author": 1,
        "date_gmt": "2026-01-15T10:00:00",
        "modified_gmt": "2026-01-16T12:00:00",
    }
    row = post_to_content("main", raw)
    assert row.post_content == "<p>Rendered only</p>"
    out = content_row_to_export_dict(row, [], _terms_lookup([]))
    assert out["post_content"] == "<p>Rendered only</p>"
    assert "content_raw" not in out
    return True


def test_mapping_from_fixed_api_post_with_yoast() -> bool:
    """Маппинг из фиксированного примера API поста с yoast_head_json."""
    raw = {
        "id": 10,
        "title": {"rendered": "Post With SEO"},
        "slug": "post-seo",
        "content": {"rendered": "<p>Body</p>"},
        "excerpt": {"rendered": "Excerpt"},
        "status": "publish",
        "author": 2,
        "date_gmt": "2026-02-01T08:00:00",
        "modified_gmt": "2026-02-02T09:00:00",
        "yoast_head_json": {"title": "SEO Title", "og_description": "Meta desc"},
    }
    row = post_to_content("main", raw)
    terms = content_embedded_terms("main", "post", 10, raw)
    out = content_row_to_export_dict(row, terms, _terms_lookup([]))
    assert out["wp_id"] == 10
    assert out["slug"] == "post-seo"
    assert out["title"] == "Post With SEO"
    assert out["post_content"] == "<p>Body</p>"
    assert out["seo"]["seo_title"] == "SEO Title"
    assert out["seo"]["seo_description"] == "Meta desc"
    assert out["seo"]["yoast_head_json"]["title"] == "SEO Title"
    return True


def test_summary_no_credentials() -> bool:
    """summary_to_export_dict не содержит полей с секретами."""
    summary = {"run_id": "r1", "site_id": "main", "status": "success", "run_at": "2026-01-01T00:00:00", "error_code": None, "posts_count": 0, "pages_count": 0, "terms_count": 0, "authors_count": 0, "user": "secret", "app_password": "secret"}
    out = summary_to_export_dict(summary)
    assert "user" not in out
    assert "app_password" not in out
    assert out["run_id"] == "r1"
    return True


def run_all() -> bool:
    cases = [
        ("content export full", test_content_export_full),
        ("content export without SEO", test_content_export_without_seo),
        ("content export with SEO", test_content_export_with_seo),
        ("content export without excerpt/content", test_content_export_without_excerpt_content),
        ("content export empty taxonomies", test_content_export_empty_taxonomies),
        ("single-site output is object", test_single_site_output_is_object),
        ("multi-site output is array", test_multi_site_output_is_array),
        ("multisite aggregated format", test_multisite_aggregated_format),
        ("required keys present", test_required_keys_present),
        ("post_content only rendered", test_post_content_only_rendered),
        ("mapping from fixed API post with yoast", test_mapping_from_fixed_api_post_with_yoast),
        ("summary no credentials", test_summary_no_credentials),
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
    print("WP output (stage 4) unit tests")
    sys.exit(0 if run_all() else 1)
