"""
Контракты данных Phase 3: нормализованное сообщение и медиа.

Позволяет подключать разные источники (SourceAdapter) и приёмники (DestinationAdapter)
через единый формат ContentItem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MediaItem:
    """Нормализованный элемент медиа."""

    type: str  # "photo" | "video" | "document"
    path: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    sha256: Optional[str] = None
    error: Optional[str] = None  # file_reference_expired | download_timeout | retry_exhausted


@dataclass
class ContentItem:
    """Нормализованное сообщение для обмена между Source и Destination."""

    source_id: str  # идентификатор источника, напр. "telegram:-100123" или username
    external_id: str  # id сообщения в источнике
    published_at: str  # ISO UTC
    text: str
    media: List[MediaItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # views, forwards, forwarded, reply_to_msg_id и т.д.


def tg_message_to_content_item(msg: Dict[str, Any], source_id: str) -> ContentItem:
    """Преобразовать текущий словарь сообщения TG (export.json) в нормализованный ContentItem."""
    media: List[MediaItem] = []
    for m in msg.get("media_files") or []:
        media.append(
            MediaItem(
                type=m.get("type", "document"),
                path=m.get("path"),
                filename=m.get("filename"),
                size=m.get("size"),
                sha256=m.get("sha256"),
                error=m.get("error"),
            )
        )
    metadata: Dict[str, Any] = {}
    for key in ("forwarded", "reply_to_msg_id", "views", "forwards"):
        if key in msg and msg[key] is not None:
            metadata[key] = msg[key]
    return ContentItem(
        source_id=source_id,
        external_id=str(msg.get("id", "")),
        published_at=msg.get("date") or "",
        text=msg.get("text") or "",
        media=media,
        metadata=metadata,
    )


def content_item_to_tg_message(item: ContentItem) -> Dict[str, Any]:
    """Преобразовать ContentItem обратно в формат сообщения TG (для export.json)."""
    media_files: List[Dict[str, Any]] = []
    for m in item.media:
        d: Dict[str, Any] = {"type": m.type, "path": m.path, "filename": m.filename}
        if m.size is not None:
            d["size"] = m.size
        if m.sha256 is not None:
            d["sha256"] = m.sha256
        if m.error is not None:
            d["error"] = m.error
        media_files.append(d)
    out: Dict[str, Any] = {
        "id": int(item.external_id) if item.external_id.isdigit() else item.external_id,
        "date": item.published_at,
        "text": item.text,
        "media_files": media_files,
    }
    if "forwarded" in item.metadata:
        out["forwarded"] = item.metadata["forwarded"]
    if "reply_to_msg_id" in item.metadata:
        out["reply_to_msg_id"] = item.metadata["reply_to_msg_id"]
    if "views" in item.metadata:
        out["views"] = item.metadata["views"]
    if "forwards" in item.metadata:
        out["forwards"] = item.metadata["forwards"]
    return out
