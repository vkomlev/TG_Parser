"""Маппинг ответов WP REST API в внутренние структуры для БД и JSON output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AuthorRow:
    site_id: str
    wp_user_id: int
    login: Optional[str]
    name: Optional[str]
    slug: Optional[str]
    raw_json: Optional[Dict[str, Any]]


@dataclass
class TermRow:
    site_id: str
    taxonomy: str
    wp_term_id: int
    name: Optional[str]
    slug: str
    parent_id: Optional[int]
    raw_json: Optional[Dict[str, Any]]


@dataclass
class ContentRow:
    site_id: str
    content_type: str  # 'post' | 'page'
    wp_id: int
    title: Optional[str]
    slug: str
    post_content: Optional[str]
    excerpt: Optional[str]
    status: str
    author_id: Optional[int]
    published_at: Optional[datetime]
    modified_at: Optional[datetime]
    seo_title: Optional[str]
    seo_description: Optional[str]
    seo_json: Optional[Dict[str, Any]]
    raw_json: Optional[Dict[str, Any]]


@dataclass
class ContentTermRow:
    site_id: str
    content_type: str
    wp_content_id: int
    taxonomy: str
    wp_term_id: int


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _rendered_str(obj: Any, key: str) -> Optional[str]:
    v = (obj or {}).get(key)
    if v is None:
        return None
    if isinstance(v, dict) and "rendered" in v:
        s = v.get("rendered")
        return (s or "").strip() or None
    return str(v).strip() or None


def user_to_author(site_id: str, raw: Dict[str, Any]) -> AuthorRow:
    """WP /wp/v2/users item -> AuthorRow."""
    wp_id = int(raw.get("id", 0))
    login = raw.get("username") or raw.get("slug")
    name = raw.get("name")
    slug = raw.get("slug")
    return AuthorRow(
        site_id=site_id,
        wp_user_id=wp_id,
        login=str(login).strip() if login else None,
        name=str(name).strip() if name else None,
        slug=str(slug).strip() if slug else None,
        raw_json=raw,
    )


def category_to_term(site_id: str, raw: Dict[str, Any]) -> TermRow:
    """WP /wp/v2/categories item -> TermRow."""
    return _raw_term_to_row(site_id, "category", raw)


def tag_to_term(site_id: str, raw: Dict[str, Any]) -> TermRow:
    """WP /wp/v2/tags item -> TermRow."""
    return _raw_term_to_row(site_id, "post_tag", raw)


def _raw_term_to_row(site_id: str, taxonomy: str, raw: Dict[str, Any]) -> TermRow:
    wp_id = int(raw.get("id", 0))
    name = raw.get("name")
    slug = raw.get("slug") or ""
    parent = raw.get("parent")
    parent_id = int(parent) if parent is not None and parent != 0 else None
    return TermRow(
        site_id=site_id,
        taxonomy=taxonomy,
        wp_term_id=wp_id,
        name=str(name).strip() if name else None,
        slug=str(slug).strip(),
        parent_id=parent_id,
        raw_json=raw,
    )


def _extract_seo(raw: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[Dict]]:
    yoast = raw.get("yoast_head_json")
    if isinstance(yoast, dict):
        return (
            (yoast.get("title") or "").strip() or None,
            (yoast.get("og_description") or yoast.get("description") or "").strip() or None,
            yoast,
        )
    return None, None, None


def post_to_content(site_id: str, raw: Dict[str, Any]) -> ContentRow:
    """WP /wp/v2/posts item -> ContentRow (content_type='post')."""
    return _raw_to_content(site_id, "post", raw)


def page_to_content(site_id: str, raw: Dict[str, Any]) -> ContentRow:
    """WP /wp/v2/pages item -> ContentRow (content_type='page')."""
    return _raw_to_content(site_id, "page", raw)


def _raw_to_content(site_id: str, content_type: str, raw: Dict[str, Any]) -> ContentRow:
    wp_id = int(raw.get("id", 0))
    title = _rendered_str(raw, "title")
    slug = (raw.get("slug") or "").strip() or str(wp_id)
    content_rendered = (raw.get("content") or {}).get("rendered") if isinstance(raw.get("content"), dict) else None
    post_content = (content_rendered or "").strip() or None
    excerpt_rendered = (raw.get("excerpt") or {}).get("rendered") if isinstance(raw.get("excerpt"), dict) else None
    excerpt = (excerpt_rendered or "").strip() or None
    status = (raw.get("status") or "publish").strip()
    author = raw.get("author")
    author_id = int(author) if author is not None else None
    published_at = _parse_iso(raw.get("date_gmt") or raw.get("date"))
    modified_at = _parse_iso(raw.get("modified_gmt") or raw.get("modified"))
    seo_title, seo_description, seo_json = _extract_seo(raw)
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
        published_at=published_at,
        modified_at=modified_at,
        seo_title=seo_title,
        seo_description=seo_description,
        seo_json=seo_json,
        raw_json=raw,
    )


def content_embedded_terms(site_id: str, content_type: str, wp_content_id: int, raw: Dict[str, Any]) -> List[ContentTermRow]:
    """Из ответа поста/страницы с _embed извлечь связи с терминами для wp_content_terms."""
    out: List[ContentTermRow] = []
    embedded = raw.get("_embedded") or {}
    wp_term = embedded.get("wp:term")
    if not isinstance(wp_term, list):
        return out
    # wp:term — массив массивов по таксономиям: [ [categories...], [tags...] ]
    taxonomies = ["category", "post_tag"]
    for i, tax in enumerate(taxonomies):
        terms_list = wp_term[i] if i < len(wp_term) else []
        if not isinstance(terms_list, list):
            continue
        for t in terms_list:
            if isinstance(t, dict) and "id" in t:
                out.append(ContentTermRow(
                    site_id=site_id,
                    content_type=content_type,
                    wp_content_id=wp_content_id,
                    taxonomy=tax,
                    wp_term_id=int(t["id"]),
                ))
    return out
