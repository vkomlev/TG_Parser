#!/usr/bin/env python3
"""Telegram Channel Parser CLI"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# local import
sys.path.append(os.path.dirname(__file__))
from telegram_parser import TelegramParser  # noqa: E402


DEFAULT_OUTPUT = "D:\\clawbot\\ClawBot\\outbox\\telegram-parser\\"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Telegram channel parser to JSON + media")
    p.add_argument("command", choices=["channels", "parse"], help="Command")
    p.add_argument("--channel", type=str, help="Channel username, id, or link")
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
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH are required in .env")
        return 1

    parser = TelegramParser(api_id=api_id, api_hash=api_hash, session_file=args.session_file)

    try:
        if args.command == "channels":
            channels = await parser.get_available_channels()
            print(json.dumps(channels, ensure_ascii=False, indent=2))
            return 0

        if args.command == "parse":
            if not args.channel:
                print("Error: --channel is required for parse")
                return 1

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

            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        return 1
    finally:
        await parser.disconnect()


def main() -> int:
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    args = build_parser().parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Interrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
