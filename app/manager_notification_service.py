from __future__ import annotations

from typing import Any, Callable

from app import manager_notifications
from app.assistant import order_messages
from app.avito_payload import message_text
from app.config import Settings


async def notify_manager_handoff(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    handoff_reason: str | None,
    received_text: str | None,
) -> dict[str, object]:
    text = manager_notifications._format_manager_telegram_message(
        title="Нужен менеджер",
        chat=chat or {"id": chat_id},
        chat_id=chat_id,
        message_text_value=received_text,
        reason=handoff_reason,
    )
    return await manager_notifications._send_telegram_notification(settings, text)


async def notify_manager_folder_messages(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    messages_response: dict[str, Any],
    notified_state: dict[str, set[str]],
    message_processing_key: Callable[[dict[str, Any]], str],
    mark_notified_message: Callable[[dict[str, set[str]], str, dict[str, Any]], None],
    save_notified_state: Callable[[dict[str, set[str]]], None],
    record_admin_log: Callable[[str, str, Any | None], None],
    record_manager_action: Callable[[str, str, dict[str, Any]], None],
) -> dict[str, object]:
    notified_count = 0
    errors: list[object] = []
    inbound_messages = [
        message
        for message in order_messages(list(messages_response.get("messages", [])))
        if message.get("direction") == "in" and message.get("type") != "system"
    ]
    if not inbound_messages:
        return {"notified_count": 0, "errors": errors}

    if chat_id not in notified_state:
        notified_state[chat_id] = set()
        for message in inbound_messages[:-1]:
            notified_state[chat_id].add(message_processing_key(message))
        if inbound_messages[:-1]:
            save_notified_state(notified_state)

    for message in inbound_messages:
        message_key = message_processing_key(message)
        if message_key in notified_state.get(chat_id, set()):
            continue
        text = manager_notifications._format_manager_telegram_message(
            title="Новое сообщение в менеджерской папке",
            chat=chat or {"id": chat_id},
            chat_id=chat_id,
            message_text_value=message_text(message),
            reason=manager_notifications._telegram_reason_for_manager_folder_chat(chat or {}),
        )
        notification = await manager_notifications._send_telegram_notification(settings, text)
        record_admin_log(
            "info",
            "manager_notification_attempted",
            {"chat_id": chat_id, "message_key": message_key, "status": notification.get("status")},
        )
        record_manager_action(
            chat_id,
            "manager_message_notified",
            {
                "message_key": message_key,
                "received_text": message_text(message),
                "manager_notification": notification,
            },
        )
        if notification.get("status") == "failed":
            errors.append(notification.get("error") or notification)
            continue
        mark_notified_message(notified_state, chat_id, message)
        if notification.get("status") != "skipped":
            notified_count += 1
    return {"notified_count": notified_count, "errors": errors}


async def notify_inbound_messages(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    messages_response: dict[str, Any],
    notified_state: dict[str, set[str]],
    message_processing_key: Callable[[dict[str, Any]], str],
    mark_notified_message: Callable[[dict[str, set[str]], str, dict[str, Any]], None],
    record_admin_log: Callable[[str, str, Any | None], None],
    record_manager_action: Callable[[str, str, dict[str, Any]], None],
) -> dict[str, object]:
    notified_count = 0
    errors: list[object] = []
    inbound_messages = [
        message
        for message in order_messages(list(messages_response.get("messages", [])))
        if message.get("direction") == "in" and message.get("type") != "system"
    ]
    if chat_id not in notified_state:
        notified_state[chat_id] = set()
        for message in inbound_messages[:-1]:
            mark_notified_message(notified_state, chat_id, message)

    for message in inbound_messages:
        message_key = message_processing_key(message)
        if message_key in notified_state.get(chat_id, set()):
            continue
        text = manager_notifications._format_manager_telegram_message(
            title="Новое сообщение от клиента",
            chat=chat or {"id": chat_id},
            chat_id=chat_id,
            message_text_value=message_text(message),
            reason="новое входящее",
        )
        notification = await manager_notifications._send_telegram_notification(settings, text)
        record_admin_log(
            "info",
            "telegram_inbound_notification_attempted",
            {"chat_id": chat_id, "message_key": message_key, "status": notification.get("status")},
        )
        if notification.get("status") != "skipped":
            record_manager_action(
                chat_id,
                "telegram_inbound_notified",
                {
                    "message_key": message_key,
                    "received_text": message_text(message),
                    "manager_notification": notification,
                },
            )
        if notification.get("status") == "failed":
            errors.append(notification.get("error") or notification)
            continue
        mark_notified_message(notified_state, chat_id, message)
        if notification.get("status") != "skipped":
            notified_count += 1
    return {"notified_count": notified_count, "errors": errors}
