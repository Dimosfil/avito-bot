from __future__ import annotations

from typing import Any


def chat_item_context(chat: dict[str, Any]) -> dict[str, Any]:
    context = chat.get("context")
    if isinstance(context, dict) and isinstance(context.get("value"), dict):
        return context["value"]
    item = chat.get("item")
    if isinstance(item, dict):
        return item
    return {}


def chat_item_key(chat: dict[str, Any]) -> str:
    item = chat_item_context(chat)
    value = (
        item.get("id")
        or item.get("item_id")
        or item.get("avito_id")
        or chat.get("item_id")
        or chat.get("itemId")
        or item.get("url")
        or item.get("uri")
        or item.get("link")
        or item.get("external_url")
    )
    if value:
        return str(value)
    title = item.get("title") or chat.get("context", {}).get("title") or ""
    price = item.get("price_string") or ""
    fallback = f"{title}|{price}".strip("|")
    return fallback or ""


def message_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def author_role(direction: Any) -> str | None:
    if direction == "in":
        return "client"
    if direction == "out":
        return "seller"
    return None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
