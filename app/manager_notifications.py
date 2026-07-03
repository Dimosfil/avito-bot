from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


def _format_manager_telegram_message(
    *,
    title: str,
    chat: dict[str, Any],
    chat_id: str,
    message_text_value: str | None,
    reason: str | None,
) -> str:
    item_title = _telegram_item_title(chat)
    item_url = _telegram_item_url(chat)
    profile_url = _telegram_client_profile_url(chat)
    local_url = _manager_local_chat_url(chat_id)

    lines = [
        title,
        "",
        "Канал: Avito",
        f"Чат: {chat_id}",
        f"Клиент: {_telegram_client_name(chat)}",
        f"Объявление: {item_title}",
        f"Причина: {reason or _telegram_reason_for_manager_folder_chat(chat) or 'не указана'}",
        "",
        "Последнее сообщение:",
        message_text_value or "без текста",
    ]
    if profile_url:
        lines.extend(["", f"Профиль клиента: {profile_url}"])
    if item_url:
        lines.append(f"Объявление Avito: {item_url}")
    if local_url:
        lines.append(f"Ссылка: {local_url}")
    return "\n".join(lines)


def _telegram_client_name(chat: dict[str, Any]) -> str:
    item = _telegram_item_context(chat)
    seller_id = _string_id(item.get("user_id") or chat.get("seller_id") or chat.get("owner_id") or chat.get("account_id"))
    title = _clean_text(chat.get("title") or chat.get("name") or chat.get("display_name") or chat.get("chat_title"))
    item_title = _telegram_item_title(chat)
    if title and title != item_title:
        return title

    direct_name = _pick_person_name(chat.get("buyer") or chat.get("client") or chat.get("customer") or chat.get("sender"))
    if direct_name:
        return direct_name

    for user in _telegram_chat_users(chat):
        user_id = _string_id(user.get("id") or user.get("user_id") or user.get("author_id") or (user.get("public_user_profile") or {}).get("user_id"))
        if seller_id and user_id == seller_id:
            continue
        name = _pick_person_name(user)
        if name:
            return name
    return "не определен"


def _telegram_item_title(chat: dict[str, Any]) -> str:
    item = _telegram_item_context(chat)
    return _clean_text(item.get("title") or (chat.get("context") or {}).get("title") or chat.get("item_title")) or "не определено"


def _telegram_item_url(chat: dict[str, Any]) -> str:
    item = _telegram_item_context(chat)
    return _clean_text(
        item.get("url")
        or item.get("uri")
        or item.get("link")
        or item.get("external_url")
        or chat.get("item_url")
        or chat.get("item_link")
    )


def _telegram_client_profile_url(chat: dict[str, Any]) -> str:
    direct_url = _clean_text(
        (chat.get("buyer") or {}).get("profile_url")
        or (chat.get("buyer") or {}).get("url")
        or (chat.get("client") or {}).get("profile_url")
        or (chat.get("client") or {}).get("url")
        or (chat.get("user") or {}).get("profile_url")
        or (chat.get("user") or {}).get("url")
    )
    if direct_url:
        return direct_url
    for user in _telegram_chat_users(chat):
        url = _clean_text(user.get("profile_url") or user.get("url") or (user.get("public_user_profile") or {}).get("url"))
        if url:
            return url
    return ""


def _telegram_reason_for_manager_folder_chat(chat: dict[str, Any]) -> str:
    signals = [
        chat.get("handoff_reason"),
        chat.get("handoff_status"),
        chat.get("deal_status"),
        chat.get("order_status"),
    ]
    for signal in signals:
        value = _clean_text(signal)
        if value:
            return value
    return "менеджерская папка"


def _manager_local_chat_url(chat_id: str) -> str:
    if not chat_id:
        return "http://127.0.0.1:8000"
    return f"http://127.0.0.1:8000/?chat={chat_id}"


def _telegram_item_context(chat: dict[str, Any]) -> dict[str, Any]:
    context = chat.get("context")
    if isinstance(context, dict) and isinstance(context.get("value"), dict):
        return context["value"]
    item = chat.get("item")
    if isinstance(item, dict):
        return item
    return {}


def _telegram_chat_users(chat: dict[str, Any]) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    for source in (chat.get("users"), chat.get("participants"), chat.get("members"), (chat.get("context") or {}).get("users")):
        if isinstance(source, list):
            users.extend(user for user in source if isinstance(user, dict))
    return users


def _pick_person_name(person: object) -> str:
    if not isinstance(person, dict):
        return ""
    return _clean_text(
        person.get("name")
        or person.get("display_name")
        or person.get("title")
        or (person.get("profile") or {}).get("name")
        or (person.get("public_user_profile") or {}).get("name")
    )


def _clean_text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _string_id(value: object) -> str:
    return "" if value is None else str(value)


async def _send_telegram_notification(settings: Settings, text: str) -> dict[str, object]:
    if not settings.telegram_bot_token or not settings.manager_telegram_chat_id:
        return {"status": "skipped", "reason": "telegram_not_configured"}

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.manager_telegram_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.telegram_notify_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except Exception as exc:  # notification must not block Avito processing
        return {"status": "failed", "error": _error_detail(exc)}
    return {"status": "sent"}


def _error_detail(exc: Exception) -> object:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json()
        except ValueError:
            return exc.response.text
    return str(exc) or exc.__class__.__name__
