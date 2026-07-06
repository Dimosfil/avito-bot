from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.assistant import order_messages
from app.avito_client import AvitoClient
from app.avito_payload import chat_item_key, message_text
from app.bot_rules import has_buying_intent
from app.storage import RuntimeStore


@dataclass(frozen=True)
class AvitoSyncServices:
    get_runtime_store: Callable[[], RuntimeStore]
    record_admin_log: Callable[[str, str, Any | None], None]
    error_detail: Callable[[Exception], object]
    load_qualified_buying_chat_ids: Callable[[], set[str]]
    save_qualified_buying_chat_ids: Callable[[set[str]], None]
    clear_automatic_takeover_for_qualified_chats: Callable[[set[str]], None]
    ensure_bot_control_state_loaded: Callable[[], None]
    save_bot_control_state: Callable[[], None]
    known_bot_control_chat_ids: set[str]
    known_bot_control_item_keys: set[str]
    bot_control_state_path: Path


def persist_avito_chats(chats: list[dict[str, Any]], services: AvitoSyncServices) -> None:
    try:
        services.get_runtime_store().upsert_avito_chats(chats)
        services.record_admin_log("info", "chats_persisted", {"count": len(chats)})
    except Exception as exc:
        services.record_admin_log(
            "error",
            "chat_persistence_failed",
            {"count": len(chats), "error": services.error_detail(exc)},
        )


def persist_avito_messages(
    chat_id: str,
    messages_response: dict[str, Any],
    services: AvitoSyncServices,
) -> None:
    messages = list(messages_response.get("messages", []))
    if not messages:
        return
    try:
        services.get_runtime_store().upsert_avito_messages(chat_id, messages)
        services.record_admin_log("info", "messages_persisted", {"chat_id": chat_id, "count": len(messages)})
    except Exception as exc:
        services.record_admin_log(
            "error",
            "message_persistence_failed",
            {"chat_id": chat_id, "count": len(messages), "error": services.error_detail(exc)},
        )


async def sync_qualified_buying_from_chats(
    client: AvitoClient,
    chats: list[dict[str, Any]],
    services: AvitoSyncServices,
) -> list[str]:
    chat_ids = services.load_qualified_buying_chat_ids()
    changed_chat_ids: set[str] = set()
    chats_to_inspect: list[tuple[str, dict[str, Any]]] = []
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id or chat_id in chat_ids:
            continue
        if chat_summary_has_buying_intent(chat):
            changed_chat_ids.add(chat_id)
            continue
        chats_to_inspect.append((chat_id, chat))

    semaphore = asyncio.Semaphore(5)

    async def inspect_chat_messages(chat_id: str) -> str | None:
        async with semaphore:
            try:
                messages = await client.get_messages(chat_id, limit=50)
            except Exception as exc:
                services.record_admin_log(
                    "warning",
                    "qualified_buying_inspection_failed",
                    {"chat_id": chat_id, "error": services.error_detail(exc)},
                )
                return None
            persist_avito_messages(chat_id, messages, services)
            return chat_id if messages_have_buying_intent(messages) else None

    if chats_to_inspect:
        inspected_ids = await asyncio.gather(
            *(inspect_chat_messages(chat_id) for chat_id, _chat in chats_to_inspect)
        )
        changed_chat_ids.update(chat_id for chat_id in inspected_ids if chat_id)

    if changed_chat_ids:
        chat_ids.update(changed_chat_ids)
        services.save_qualified_buying_chat_ids(chat_ids)
    services.clear_automatic_takeover_for_qualified_chats(chat_ids)
    return sorted(chat_ids)


def chat_summary_has_buying_intent(chat: dict[str, Any]) -> bool:
    last_message = chat.get("last_message")
    if not isinstance(last_message, dict) or last_message.get("direction") != "in":
        return False
    return has_buying_intent(message_text(last_message) or "")


def messages_have_buying_intent(messages_response: dict[str, Any]) -> bool:
    client_texts = [
        message_text(message) or ""
        for message in order_messages(list(messages_response.get("messages", [])))
        if message.get("direction") == "in" and message.get("type") != "system"
    ]
    return has_buying_intent("\n".join(client_texts))


def track_bot_control_items(chats: list[dict[str, Any]], services: AvitoSyncServices) -> None:
    services.ensure_bot_control_state_loaded()
    chat_ids_by_item_key: dict[str, list[str]] = {}
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        item_key = chat_item_key(chat)
        if not chat_id or not item_key:
            continue
        chat_ids_by_item_key.setdefault(item_key, []).append(chat_id)

    if not chat_ids_by_item_key:
        return

    changed = False
    if not services.known_bot_control_item_keys and not services.bot_control_state_path.exists():
        services.known_bot_control_item_keys.update(chat_ids_by_item_key)
        services.known_bot_control_chat_ids.update(
            chat_id for chat_ids in chat_ids_by_item_key.values() for chat_id in chat_ids
        )
        changed = True
    else:
        for item_key, chat_ids in chat_ids_by_item_key.items():
            is_new_item = item_key not in services.known_bot_control_item_keys
            services.known_bot_control_item_keys.add(item_key)
            for chat_id in chat_ids:
                if chat_id not in services.known_bot_control_chat_ids:
                    services.known_bot_control_chat_ids.add(chat_id)
                    changed = True
            if is_new_item:
                changed = True

    if changed:
        services.save_bot_control_state()
