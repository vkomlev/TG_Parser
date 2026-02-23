"""Загрузка users, terms, posts, pages из WP REST API с пагинацией.

Этап 3: пагинация по X-WP-TotalPages с fallback, фильтры status=publish и _embed,
маппинг в AuthorRow/TermRow/ContentRow/ContentTermRow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .client import WPRestClient
from .mapper import (
    AuthorRow,
    ContentRow,
    ContentTermRow,
    TermRow,
    category_to_term,
    content_embedded_terms,
    page_to_content,
    post_to_content,
    tag_to_term,
    user_to_author,
)

logger = logging.getLogger("wp.fetcher")


def _total_pages(headers: Optional[Dict[str, Any]]) -> int:
    """Число страниц из X-WP-TotalPages. Защита от невалидных значений: не падать, возвращать >= 1."""
    if not headers:
        return 1
    try:
        raw = headers.get("X-WP-TotalPages") or headers.get("x-wp-totalpages") or 1
        n = int(raw)
        return max(1, n)
    except (ValueError, TypeError):
        return 1


def fetch_users(
    client: WPRestClient,
    site_id: str,
    per_page: int = 100,
    run_id: Optional[str] = None,
) -> List[AuthorRow]:
    """Загрузить всех пользователей (авторов). GET /users с пагинацией."""
    result: List[AuthorRow] = []
    page = 1
    while True:
        data, headers = client.get_with_headers(
            "/users",
            params={"per_page": per_page, "page": page},
            run_id=run_id,
        )
        if not isinstance(data, list):
            logger.warning(
                "WP API /users вернул не список (type=%s), завершаем пагинацию",
                type(data).__name__,
                extra={"site_id": site_id, "run_id": run_id},
            )
            break
        for item in data:
            if isinstance(item, dict):
                result.append(user_to_author(site_id, item))
        total_pages = _total_pages(headers)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
    return result


def fetch_categories(
    client: WPRestClient,
    site_id: str,
    per_page: int = 100,
    run_id: Optional[str] = None,
) -> List[TermRow]:
    """Загрузить все категории. GET /categories с пагинацией."""
    result: List[TermRow] = []
    page = 1
    while True:
        data, headers = client.get_with_headers(
            "/categories",
            params={"per_page": per_page, "page": page},
            run_id=run_id,
        )
        if not isinstance(data, list):
            logger.warning(
                "WP API /categories вернул не список (type=%s), завершаем пагинацию",
                type(data).__name__,
                extra={"site_id": site_id, "run_id": run_id},
            )
            break
        for item in data:
            if isinstance(item, dict):
                result.append(category_to_term(site_id, item))
        total_pages = _total_pages(headers)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
    return result


def fetch_tags(
    client: WPRestClient,
    site_id: str,
    per_page: int = 100,
    run_id: Optional[str] = None,
) -> List[TermRow]:
    """Загрузить все теги. GET /tags с пагинацией."""
    result: List[TermRow] = []
    page = 1
    while True:
        data, headers = client.get_with_headers(
            "/tags",
            params={"per_page": per_page, "page": page},
            run_id=run_id,
        )
        if not isinstance(data, list):
            logger.warning(
                "WP API /tags вернул не список (type=%s), завершаем пагинацию",
                type(data).__name__,
                extra={"site_id": site_id, "run_id": run_id},
            )
            break
        for item in data:
            if isinstance(item, dict):
                result.append(tag_to_term(site_id, item))
        total_pages = _total_pages(headers)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
    return result


def fetch_posts(
    client: WPRestClient,
    site_id: str,
    per_page: int = 100,
    run_id: Optional[str] = None,
) -> Tuple[List[ContentRow], List[ContentTermRow]]:
    """Загрузить все посты (status=publish) с _embed. Возвращает (content_rows, content_term_rows)."""
    contents: List[ContentRow] = []
    content_terms: List[ContentTermRow] = []
    page = 1
    while True:
        data, headers = client.get_with_headers(
            "/posts",
            params={
                "status": "publish",
                "per_page": per_page,
                "page": page,
                "_embed": "",
            },
            run_id=run_id,
        )
        if not isinstance(data, list):
            logger.warning(
                "WP API /posts вернул не список (type=%s), завершаем пагинацию",
                type(data).__name__,
                extra={"site_id": site_id, "run_id": run_id},
            )
            break
        for item in data:
            if not isinstance(item, dict):
                continue
            contents.append(post_to_content(site_id, item))
            content_terms.extend(
                content_embedded_terms(site_id, "post", int(item.get("id", 0)), item)
            )
        total_pages = _total_pages(headers)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
    return contents, content_terms


def fetch_pages(
    client: WPRestClient,
    site_id: str,
    per_page: int = 100,
    run_id: Optional[str] = None,
) -> Tuple[List[ContentRow], List[ContentTermRow]]:
    """Загрузить все страницы (status=publish) с _embed. Возвращает (content_rows, content_term_rows)."""
    contents: List[ContentRow] = []
    content_terms: List[ContentTermRow] = []
    page = 1
    while True:
        data, headers = client.get_with_headers(
            "/pages",
            params={
                "status": "publish",
                "per_page": per_page,
                "page": page,
                "_embed": "",
            },
            run_id=run_id,
        )
        if not isinstance(data, list):
            logger.warning(
                "WP API /pages вернул не список (type=%s), завершаем пагинацию",
                type(data).__name__,
                extra={"site_id": site_id, "run_id": run_id},
            )
            break
        for item in data:
            if not isinstance(item, dict):
                continue
            contents.append(page_to_content(site_id, item))
            content_terms.extend(
                content_embedded_terms(site_id, "page", int(item.get("id", 0)), item)
            )
        total_pages = _total_pages(headers)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
    return contents, content_terms
