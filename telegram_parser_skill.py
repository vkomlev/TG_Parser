#!/usr/bin/env python3
"""Telegram Channel Parser CLI"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# local import
sys.path.append(os.path.dirname(__file__))
from logging_setup import setup_app_logging  # noqa: E402
from telegram_parser import TelegramParser  # noqa: E402


DEFAULT_OUTPUT = "D:\\clawbot\\ClawBot\\outbox\\telegram-parser\\"


def _configure_utf8_stdio() -> None:
    """Включить UTF-8 для stdout/stderr (важно для Windows-консоли).

    Returns:
        None.
    """

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _print_utf8(text: str) -> None:
    """Печать UTF-8 без зависимости от кодовой страницы консоли."""

    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


def _print_err_utf8(text: str) -> None:
    """Печать в stderr UTF-8 без ошибок кодировки."""

    sys.stderr.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stderr.buffer.write(b"\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Telegram channel parser to JSON + media")
    p.add_argument(
        "command",
        choices=["channels", "parse", "resolve"],
        help="Command: channels — список каналов, parse — парсинг, resolve — id по ссылке",
    )
    p.add_argument(
        "--channel",
        type=str,
        help="Канал: ссылка (t.me/channel/123), @username или числовой id",
    )
    p.add_argument("--mode", choices=["safe", "normal"], default="safe", help="Rate mode")
    p.add_argument("--date-from", type=str, help="Start date YYYY-MM-DD")
    p.add_argument("--date-to", type=str, help="End date YYYY-MM-DD")
    p.add_argument("--keyword-filter", nargs="+", help="Optional keyword filter")
    p.add_argument("--max-media-size", type=int, help="Maximum media size in MB")
    p.add_argument("--dry-run", action="store_true", help="Estimate only, no writes/downloads")
    p.add_argument("--zip", action="store_true", help="Create .zip archive")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT, help="Base output directory")
    p.add_argument("--session-file", default="telegram_session", help="Telethon session name")
    p.add_argument("--no-cleanup-temp", action="store_true", help="Keep temp files")
    return p


async def run(args: argparse.Namespace) -> int:
    log = logging.getLogger("tg_parser.cli")

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        log.error("Отсутствуют TELEGRAM_API_ID/TELEGRAM_API_HASH в .env")
        _print_err_utf8("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH are required in .env")
        return 1

    parser = TelegramParser(
        api_id=api_id,
        api_hash=api_hash,
        session_file=args.session_file,
        auth_state_dir=Path(__file__).parent / "logs",
    )

    try:
        if args.command == "channels":
            log.info("Команда channels (session_file=%s)", args.session_file)
            channels = await parser.get_available_channels()
            _print_utf8(json.dumps(channels, ensure_ascii=False, indent=2))
            return 0

        if args.command == "resolve":
            if not args.channel:
                log.error("Команда resolve без --channel")
                _print_err_utf8("Error: --channel is required for resolve (link, @username or id)")
                return 1
            log.info("Команда resolve (channel=%s)", args.channel)
            info = await parser.get_channel_info(args.channel)
            _print_utf8(json.dumps(info, ensure_ascii=False, indent=2))
            return 0

        if args.command == "parse":
            if not args.channel:
                log.error("Команда parse без --channel")
                _print_err_utf8("Error: --channel is required for parse")
                return 1

            log.info(
                "Команда parse (channel=%s, mode=%s, dry_run=%s, output_dir=%s)",
                args.channel,
                args.mode,
                args.dry_run,
                args.output_dir,
            )
            result = await parser.parse_channel(
                channel_identifier=args.channel,
                output_dir=args.output_dir,
                mode=args.mode,
                date_from=args.date_from,
                date_to=args.date_to,
                keyword_filter=args.keyword_filter,
                max_media_size_mb=args.max_media_size,
                dry_run=args.dry_run,
                zip_output=args.zip,
                cleanup_temp=not args.no_cleanup_temp,
            )

            _print_utf8(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        return 1
    except Exception:
        log.exception("Необработанная ошибка CLI")
        raise
    finally:
        await parser.disconnect()


def main() -> int:
    _configure_utf8_stdio()
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    setup_app_logging(Path(__file__).parent / "logs")
    args = build_parser().parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        logging.getLogger("tg_parser.cli").warning("Остановка по Ctrl+C")
        _print_err_utf8("Interrupted")
        return 130
    except Exception as e:
        logging.getLogger("tg_parser.cli").exception("Ошибка выполнения: %s", e)
        _print_err_utf8(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
