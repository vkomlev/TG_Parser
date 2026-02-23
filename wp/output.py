"""Единый JSON-контракт выгрузки WP Source (MVP).

Преобразование: внутренняя модель (ContentRow, TermRow, summary) -> JSON output.
Без интеграции с ContentItem (contracts.py) — только экспорт в stdout/файл.

Контракт документа контента:
  source, site_id, content_type, wp_id, slug, title, post_content, excerpt,
  status, author_id, published_at, modified_at, taxonomies, seo.
Контракт summary: run_id, site_id, status, run_at, error_code, *_count.
Отсутствующие поля отдаются как null.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .mapper import ContentRow, ContentTermRow, TermRow


def _terms_lookup(terms: List[TermRow]) -> Dict[Tuple[str, str, int], TermRow]:
    """(site_id, taxonomy, wp_term_id) -> TermRow."""
    out: Dict[Tuple[str, str, int], TermRow] = {}
    for t in terms:
        out[(t.site_id, t.taxonomy, t.wp_term_id)] = t
    return out


def _taxonomies_for_content(
    site_id: str,
    content_type: str,
    wp_content_id: int,
    content_terms: List[ContentTermRow],
    terms_lookup: Dict[Tuple[str, str, int], TermRow],
) -> Dict[str, List[Dict[str, Any]]]:
    """Машинночитаемый вид: { "category": [{wp_term_id, slug, name}], "post_tag": [...] }."""
    by_tax: Dict[str, List[Dict[str, Any]]] = {"category": [], "post_tag": []}
    for ct in content_terms:
        if ct.site_id != site_id or ct.content_type != content_type or ct.wp_content_id != wp_content_id:
            continue
        key = (site_id, ct.taxonomy, ct.wp_term_id)
        term = terms_lookup.get(key)
        slug = term.slug if term else None
        name = term.name if term else None
        by_tax.setdefault(ct.taxonomy, []).append({
            "wp_term_id": ct.wp_term_id,
            "slug": slug,
            "name": name,
        })
    return by_tax


def _datetime_iso(d: Optional[datetime]) -> Optional[str]:
    if d is None:
        return None
    return d.isoformat()


def content_row_to_export_dict(
    row: ContentRow,
    content_terms: List[ContentTermRow],
    terms_lookup: Dict[Tuple[str, str, int], TermRow],
) -> Dict[str, Any]:
    """ContentRow -> словарь по единому JSON-контракту (без секретов)."""
    taxonomies = _taxonomies_for_content(
        row.site_id, row.content_type, row.wp_id, content_terms, terms_lookup
    )
    return {
        "source": "wp",
        "site_id": row.site_id,
        "content_type": row.content_type,
        "wp_id": row.wp_id,
        "slug": row.slug,
        "title": row.title,
        "post_content": row.post_content,
        "excerpt": row.excerpt,
        "status": row.status,
        "author_id": row.author_id,
        "published_at": _datetime_iso(row.published_at),
        "modified_at": _datetime_iso(row.modified_at),
        "taxonomies": taxonomies,
        "seo": {
            "seo_title": row.seo_title,
            "seo_description": row.seo_description,
            "yoast_head_json": row.seo_json,
        },
    }


def build_content_export_list(
    contents: List[ContentRow],
    content_terms: List[ContentTermRow],
    terms: List[TermRow],
) -> List[Dict[str, Any]]:
    """Список контента для одного сайта в формате контракта."""
    lookup = _terms_lookup(terms)
    return [
        content_row_to_export_dict(row, content_terms, lookup)
        for row in contents
    ]


def summary_to_export_dict(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Summary run -> стабильный контракт (run_id, status, counts, error_code). Без credential-полей."""
    return {
        "run_id": summary.get("run_id"),
        "site_id": summary.get("site_id"),
        "status": summary.get("status"),
        "run_at": summary.get("run_at"),
        "error_code": summary.get("error_code"),
        "posts_count": summary.get("posts_count", 0),
        "pages_count": summary.get("pages_count", 0),
        "terms_count": summary.get("terms_count", 0),
        "authors_count": summary.get("authors_count", 0),
    }


def build_single_site_output(
    summary: Dict[str, Any],
    content_export: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Один сайт: объект с summary-полями и массивом content."""
    out = summary_to_export_dict(summary)
    out["content"] = content_export
    return out


def build_multi_site_output(sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Несколько сайтов: массив объектов (каждый как build_single_site_output)."""
    return list(sites)


def build_multisite_aggregated(
    run_id: str,
    exit_code: int,
    site_outputs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Multi-site: один объект с run_id, status, totals и массивом sites.
    exit_code: 0=success, 2=partial, 1=failed.
    """
    status = "success" if exit_code == 0 else ("partial" if exit_code == 2 else "failed")
    success_count = sum(1 for s in site_outputs if s.get("status") == "success")
    failed_count = sum(1 for s in site_outputs if s.get("status") == "failed")
    totals = {
        "sites": len(site_outputs),
        "success": success_count,
        "failed": failed_count,
        "posts_count": sum(s.get("posts_count", 0) for s in site_outputs),
        "pages_count": sum(s.get("pages_count", 0) for s in site_outputs),
        "terms_count": sum(s.get("terms_count", 0) for s in site_outputs),
        "authors_count": sum(s.get("authors_count", 0) for s in site_outputs),
    }
    return {
        "run_id": run_id,
        "status": status,
        "totals": totals,
        "sites": site_outputs,
    }
