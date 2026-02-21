#!/usr/bin/env python3
"""
Смоук-тесты Phase 3: контракты (ContentItem), маппинг TG ↔ контракт, адаптеры.

Все тесты без Telegram (моки). Запуск из корня проекта (.venv):
  python smoke_phase3.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unittest.mock import AsyncMock, patch

from contracts import (
    ContentItem,
    MediaItem,
    content_item_to_tg_message,
    tg_message_to_content_item,
)
from adapters import LocalExportDestinationAdapter, TelegramSourceAdapter
from telegram_parser import TelegramParser


OUT = Path(__file__).parent / "out_smoke_phase3"


def test1_round_trip_tg_content_tg() -> bool:
    """Контракт: TG -> ContentItem -> TG сохраняет ключевые поля (в т.ч. media.error)."""
    messages = [
        {
            "id": 101,
            "date": "2026-02-17T12:00:00Z",
            "text": "Hello",
            "media_files": [
                {"type": "photo", "path": "media/photos/1.jpg", "filename": "1.jpg", "size": 1000},
                {"type": "document", "path": None, "filename": None, "error": "file_reference_expired"},
            ],
            "forwarded": {"from_name": "X", "date": "2026-02-16T10:00:00Z"},
            "reply_to_msg_id": 99,
            "views": 100,
            "forwards": 2,
        },
        {"id": 102, "date": "2026-02-17T13:00:00Z", "text": "No media", "media_files": []},
    ]
    source_id = "telegram:test"
    for msg in messages:
        item = tg_message_to_content_item(msg, source_id)
        back = content_item_to_tg_message(item)
        if back.get("id") != msg.get("id"):
            return False
        if back.get("date") != msg.get("date"):
            return False
        if back.get("text") != msg.get("text"):
            return False
        mf = back.get("media_files") or []
        orig_mf = msg.get("media_files") or []
        if len(mf) != len(orig_mf):
            return False
        for a, b in zip(mf, orig_mf):
            if a.get("type") != b.get("type") or a.get("error") != b.get("error"):
                return False
        for key in ("forwarded", "reply_to_msg_id", "views", "forwards"):
            if msg.get(key) != back.get(key):
                return False
    return True


def test2_local_dest_mixed_external_id() -> bool:
    """LocalExportDestinationAdapter: mixed external_id (123, abc-42, '', 001) — не падает, total_messages корректен."""
    items = [
        ContentItem("src", "123", "2026-02-17T10:00:00Z", "A", []),
        ContentItem("src", "abc-42", "2026-02-17T11:00:00Z", "B", []),
        ContentItem("src", "", "2026-02-17T12:00:00Z", "C", []),
        ContentItem("src", "001", "2026-02-17T13:00:00Z", "D", []),
    ]
    export_dir = OUT / "t2"
    export_dir.mkdir(parents=True, exist_ok=True)
    dest = LocalExportDestinationAdapter()
    dest.publish_batch(items, export_dir, append=False, channel_info={"id": 1, "username": "t"})
    path = export_dir / "export.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("total_messages") != 4:
        return False
    if len(data.get("messages") or []) != 4:
        return False
    return True


async def test3_source_only_new_messages() -> bool:
    """TelegramSourceAdapter: при new_messages=[...] возвращает только их, не весь export.json."""
    new_only = [
        {"id": 1, "date": "2026-02-17T10:00:00Z", "text": "New one", "media_files": []},
        {"id": 2, "date": "2026-02-17T11:00:00Z", "text": "New two", "media_files": []},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        (export_dir / "export.json").write_text(
            json.dumps({"messages": [{"id": i, "date": "", "text": f"Old {i}", "media_files": []} for i in range(50)]}, ensure_ascii=False),
            encoding="utf-8",
        )
        result = {
            "summary": {"channel_id": 123, "channel_username": "ch"},
            "export_dir": str(export_dir),
            "new_messages": new_only,
        }
        parser = TelegramParser(api_id="1", api_hash="x", session_file="x")
        with patch.object(parser, "parse_channel", new_callable=AsyncMock, return_value=result):
            adapter = TelegramSourceAdapter(parser)
            got = await adapter.fetch_messages("dummy", tmp)
    if len(got) != 2:
        return False
    if got[0].text != "New one" or got[1].text != "New two":
        return False
    return True


async def test4_source_empty_new_messages() -> bool:
    """TelegramSourceAdapter: при new_messages=[] возвращает [], не читает export.json."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        (export_dir / "export.json").write_text(
            json.dumps({"messages": [{"id": 1, "date": "", "text": "Old", "media_files": []}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        result = {
            "summary": {"channel_id": 456, "channel_username": "ch2"},
            "export_dir": str(export_dir),
            "new_messages": [],
        }
        parser = TelegramParser(api_id="1", api_hash="x", session_file="x")
        with patch.object(parser, "parse_channel", new_callable=AsyncMock, return_value=result):
            adapter = TelegramSourceAdapter(parser)
            got = await adapter.fetch_messages("dummy", tmp)
    return got == []


async def test5_source_backward_compat() -> bool:
    """TelegramSourceAdapter: без ключа new_messages читает export.json и возвращает сообщения оттуда."""
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        messages = [
            {"id": 10, "date": "2026-02-17T10:00:00Z", "text": "A", "media_files": []},
            {"id": 11, "date": "2026-02-17T11:00:00Z", "text": "B", "media_files": []},
            {"id": 12, "date": "2026-02-17T12:00:00Z", "text": "C", "media_files": []},
        ]
        (export_dir / "export.json").write_text(
            json.dumps({"messages": messages}, ensure_ascii=False),
            encoding="utf-8",
        )
        result = {
            "summary": {"channel_id": 789, "channel_username": "ch3"},
            "export_dir": str(export_dir),
        }
        parser = TelegramParser(api_id="1", api_hash="x", session_file="x")
        with patch.object(parser, "parse_channel", new_callable=AsyncMock, return_value=result):
            adapter = TelegramSourceAdapter(parser)
            got = await adapter.fetch_messages("dummy", tmp)
    if len(got) != 3:
        return False
    if [g.text for g in got] != ["A", "B", "C"]:
        return False
    return True


def test6_local_dest_append() -> bool:
    """LocalExportDestinationAdapter: append=False пишет новый export; append=True дописывает; channel_info не теряется."""
    import shutil
    export_dir = OUT / "t6"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    channel_info = {"id": 100, "username": "channel", "title": "Test"}
    dest = LocalExportDestinationAdapter()

    dest.publish_batch(
        [ContentItem("s", "1", "2026-02-17T10:00:00Z", "First", [])],
        export_dir,
        append=False,
        channel_info=channel_info,
    )
    path = export_dir / "export.json"
    data1 = json.loads(path.read_text(encoding="utf-8"))
    if data1.get("total_messages") != 1:
        return False
    if data1.get("channel_info") != channel_info:
        return False
    date1 = data1.get("export_date")
    import time
    time.sleep(1.1)  # чтобы export_date гарантированно обновился при append

    dest.publish_batch(
        [ContentItem("s", "2", "2026-02-17T11:00:00Z", "Second", [])],
        export_dir,
        append=True,
    )
    data2 = json.loads(path.read_text(encoding="utf-8"))
    if data2.get("total_messages") != 2:
        return False
    if data2.get("channel_info") != channel_info:
        return False
    if data2.get("export_date") == date1:
        return False
    return True


def main() -> int:
    import asyncio
    results = []
    results.append(("1 round-trip TG->ContentItem->TG", test1_round_trip_tg_content_tg()))
    results.append(("2 LocalExport mixed external_id", test2_local_dest_mixed_external_id()))
    results.append(("3 Source only new_messages", asyncio.run(test3_source_only_new_messages())))
    results.append(("4 Source new_messages=[]", asyncio.run(test4_source_empty_new_messages())))
    results.append(("5 Source backward compat", asyncio.run(test5_source_backward_compat())))
    results.append(("6 LocalExport append", test6_local_dest_append()))

    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    failed = [n for n, ok in results if not ok]
    if failed:
        print("FAILED:", failed)
        return 1
    print("All Phase 3 smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
