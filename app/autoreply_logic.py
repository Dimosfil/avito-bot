from __future__ import annotations

import time
from typing import Any

from app.assistant import order_messages
from app.avito_payload import message_text, safe_int


def latest_non_system_message(messages_response: dict[str, Any]) -> dict[str, Any] | None:
    messages = order_messages(list(messages_response.get("messages", [])))
    for message in reversed(messages):
        if message.get("type") != "system":
            return message
    return None


def is_recent_chat(chat: dict[str, Any], *, now: float, lookback_seconds: int) -> bool:
    updated_at = safe_int(chat.get("updated") or chat.get("updated_at"))
    if updated_at is None:
        last_message = chat.get("last_message")
        if isinstance(last_message, dict):
            updated_at = safe_int(last_message.get("created") or last_message.get("created_at"))
    if updated_at is None:
        return False
    return updated_at >= int(now) - lookback_seconds


def message_processing_key(message: dict[str, Any]) -> str:
    message_id = message.get("id") or message.get("message_id")
    if message_id:
        return str(message_id)
    created_at = safe_int(message.get("created") or message.get("created_at")) or 0
    text = message_text(message) or ""
    return f"{created_at}:{text}"


def has_outbound_after_message(messages_response: dict[str, Any], pending_item: dict[str, Any] | None) -> bool:
    if not pending_item:
        return False
    pending_message_id = str(pending_item.get("message_id") or "")
    messages = [
        message
        for message in order_messages(list(messages_response.get("messages", [])))
        if message.get("type") != "system"
    ]
    if not pending_message_id:
        return bool(messages and messages[-1].get("direction") == "out")

    found_pending = False
    for message in messages:
        if found_pending and message.get("direction") == "out":
            return True
        if str(message.get("id") or "") == pending_message_id:
            found_pending = True
    return False


def estimate_reply_seconds(message: dict[str, Any]) -> int:
    text = ((message.get("content") or {}).get("text") or "").strip()
    return max(8, min(30, 10 + len(text) // 80 * 3))


def elapsed_ms(started_at: float, finished_at: float | None = None) -> int:
    return round(((finished_at or time.time()) - started_at) * 1000)
