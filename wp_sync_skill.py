#!/usr/bin/env python3
"""WordPress Source sync CLI: full sync в PostgreSQL (users, terms, posts, pages)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from errors import CONFIG_ERROR, WP_AUTH_ERROR  # noqa: E402
from exit_codes import EXIT_FAILURE, EXIT_PARTIAL, EXIT_SUCCESS  # noqa: E402
from logging_setup import set_run_id, setup_app_logging  # noqa: E402
from wp.client import WPClientError, WPRestClient  # noqa: E402
from wp.config import load_config, load_sites_list  # noqa: E402
from wp.fetcher import (  # noqa: E402
    fetch_categories,
    fetch_pages,
    fetch_posts,
    fetch_tags,
    fetch_users,
)
from wp.storage import (  # noqa: E402
    get_connection,
    insert_sync_run,
    update_sync_run,
    upsert_authors,
    upsert_content,
    upsert_content_terms,
    upsert_site,
    upsert_terms,
)

LOG = logging.getLogger("wp_sync.cli")


def _configure_utf8_stdio() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _print_err_utf8(text: str) -> None:
    sys.stderr.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stderr.buffer.write(b"\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WordPress full sync в PostgreSQL")
    p.add_argument(
        "command",
        choices=["sync", "list-sites"],
        help="sync — полная синхронизация; list-sites — список сайтов из конфига",
    )
    p.add_argument(
        "--site",
        type=str,
        help="site_id для sync (если не указан — синхронизируются все сайты из конфига)",
    )
    p.add_argument(
        "--config",
        type=str,
        default=None,
        help="Путь к config/wp-sites.yml (по умолчанию config/wp-sites.yml в корне проекта)",
    )
    return p


def run_list_sites(args: argparse.Namespace) -> int:
    project_root = Path(__file__).resolve().parent
    config_path = Path(args.config) if args.config else project_root / "config" / "wp-sites.yml"
    if not config_path.exists():
        _print_err_utf8(f"Error: config not found: {config_path}")
        return EXIT_FAILURE
    try:
        sites = load_sites_list(config_path)
    except ValueError as e:
        LOG.error("Конфиг: %s", e, extra={"error_code": CONFIG_ERROR})
        _print_err_utf8(f"Error: {e}")
        return EXIT_FAILURE
    if not sites:
        _print_err_utf8("Error: no sites in config")
        return EXIT_FAILURE
    for s in sites:
        print(json.dumps({"site_id": (s.get("site_id") or "").strip(), "base_url": (s.get("base_url") or "").strip(), "name": (s.get("name") or "").strip()}))
    return EXIT_SUCCESS


def run_sync_site(
    site_id: str,
    base_url: str,
    name: str | None,
    user: str,
    app_password: str,
    run_id: str,
    per_page: int,
    timeout_sec: int,
    retries: int,
    requests_per_second: float,
) -> dict:
    """Выполнить full sync одного сайта. Возвращает summary-словарь.
    Запись в wp_sync_runs создаётся в отдельной транзакции до сетевых вызовов,
    чтобы при ошибке sync run всегда был зафиксирован и обновлён.
    """
    started_at = datetime.now(timezone.utc)
    summary = {
        "run_id": run_id,
        "site_id": site_id,
        "run_at": started_at.isoformat(),
        "status": "success",
        "error_code": None,
        "partial_failure": False,
        "posts_count": 0,
        "pages_count": 0,
        "terms_count": 0,
        "authors_count": 0,
    }
    synced_at = started_at
    client = WPRestClient(
        base_url=base_url,
        user=user,
        app_password=app_password,
        timeout_sec=timeout_sec,
        max_retries=retries,
        requests_per_second=requests_per_second,
        site_id=site_id,
    )

    # Отдельная короткая транзакция: запись о старте run (commit сразу)
    with get_connection() as conn:
        upsert_site(conn, site_id, base_url, name)
        insert_sync_run(conn, run_id, site_id, started_at)

    def _update_run(status: str, error_code: str | None) -> None:
        with get_connection() as conn:
            n = update_sync_run(
                conn,
                run_id,
                site_id,
                datetime.now(timezone.utc),
                status,
                error_code,
                summary["posts_count"],
                summary["pages_count"],
                summary["terms_count"],
                summary["authors_count"],
            )
            if n == 0:
                LOG.warning(
                    "wp_sync_runs: UPDATE не затронул ни одной строки (run_id=%s, site_id=%s)",
                    run_id,
                    site_id,
                    extra={"site_id": site_id, "run_id": run_id},
                )

    try:
        # Сетевые вызовы вне транзакции БД
        authors = fetch_users(client, site_id, per_page=per_page, run_id=run_id)
        summary["authors_count"] = len(authors)

        categories = fetch_categories(client, site_id, per_page=per_page, run_id=run_id)
        tags = fetch_tags(client, site_id, per_page=per_page, run_id=run_id)
        all_terms = categories + tags
        summary["terms_count"] = len(all_terms)

        posts, post_terms = fetch_posts(client, site_id, per_page=per_page, run_id=run_id)
        summary["posts_count"] = len(posts)

        pages, page_terms = fetch_pages(client, site_id, per_page=per_page, run_id=run_id)
        summary["pages_count"] = len(pages)

        # Короткие транзакции на запись (без долгого удержания соединения)
        with get_connection() as conn:
            upsert_authors(conn, authors, synced_at)
        with get_connection() as conn:
            upsert_terms(conn, all_terms, synced_at)
        with get_connection() as conn:
            upsert_content(conn, posts, synced_at)
            upsert_content_terms(conn, post_terms, synced_at)
        with get_connection() as conn:
            upsert_content(conn, pages, synced_at)
            upsert_content_terms(conn, page_terms, synced_at)

        _update_run("success", None)
        return summary

    except WPClientError as e:
        summary["status"] = "failed" if summary["authors_count"] == 0 and summary["terms_count"] == 0 else "partial"
        summary["error_code"] = getattr(e, "error_code", WP_AUTH_ERROR)
        summary["partial_failure"] = summary["status"] == "partial"
        LOG.error(
            "WP sync error: %s",
            e,
            extra={"site_id": site_id, "run_id": run_id, "error_code": summary["error_code"]},
        )
        _update_run(summary["status"], summary["error_code"])
        return summary


def run_sync(args: argparse.Namespace, run_id: str) -> tuple[int, list]:
    """Возвращает (exit_code, list of summary dicts)."""
    project_root = Path(__file__).resolve().parent
    config_path = Path(args.config) if args.config else project_root / "config" / "wp-sites.yml"
    try:
        cfg = load_config(config_path=config_path, project_root=project_root)
    except ValueError as e:
        LOG.error("Конфиг: %s", e, extra={"error_code": CONFIG_ERROR})
        _print_err_utf8(f"Error: {e}")
        return EXIT_FAILURE, []

    sites = [s for s in cfg.sites if args.site is None or s.site_id == args.site]
    if not sites:
        _print_err_utf8(f"Error: site '{args.site}' not found in config")
        return EXIT_FAILURE, []

    summaries = []
    has_partial = False
    has_failure = False
    for site in sites:
        try:
            s = run_sync_site(
                site_id=site.site_id,
                base_url=site.base_url,
                name=site.name,
                user=site.user,
                app_password=site.app_password,
                run_id=run_id,
                per_page=cfg.per_page,
                timeout_sec=cfg.timeout_sec,
                retries=cfg.retries,
                requests_per_second=cfg.requests_per_second,
            )
            summaries.append(s)
            if s.get("partial_failure"):
                has_partial = True
            if s.get("status") == "failed":
                has_failure = True
        except Exception as e:
            has_failure = True
            if summaries and any(x.get("status") == "success" for x in summaries):
                has_partial = True
            summaries.append({
                "run_id": run_id,
                "site_id": site.site_id,
                "run_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed",
                "error_code": getattr(e, "error_code", None) or "CONFIG_ERROR",
                "partial_failure": False,
                "posts_count": 0,
                "pages_count": 0,
                "terms_count": 0,
                "authors_count": 0,
            })

    if has_failure and not has_partial:
        return EXIT_FAILURE, summaries
    if has_partial:
        return EXIT_PARTIAL, summaries
    return EXIT_SUCCESS, summaries


def main() -> int:
    _configure_utf8_stdio()
    project_root = Path(__file__).resolve().parent
    run_id = str(uuid.uuid4())[:8]
    logs_dir = project_root / "logs"
    setup_app_logging(logs_dir, run_id=run_id)
    set_run_id(run_id)

    args = build_parser().parse_args()

    if args.command == "list-sites":
        return run_list_sites(args)

    if args.command == "sync":
        exit_code, summaries = run_sync(args, run_id)
        if summaries:
            out = summaries[0] if len(summaries) == 1 else summaries
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return exit_code

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
