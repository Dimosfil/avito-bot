from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from app.assistant import SalesAssistant
from app.avito_client import AvitoClient
from app.avito_payload import message_text
from app.config import Settings
from app.reply_strategy import select_post_draft_strategy, select_pre_draft_strategy
from app.schemas import ProcessedUnreadChat
from app.storage import RuntimeStore


@dataclass(frozen=True)
class ProcessUnreadServices:
    settings: Settings
    avito: AvitoClient
    assistant: SalesAssistant
    get_runtime_store: Callable[[], RuntimeStore]
    to_http_error: Callable[[Exception], HTTPException]
    error_detail: Callable[[Exception], object]
    record_admin_log: Callable[[str, str, Any | None], None]
    load_autoreply_pending: Callable[[], dict[str, dict[str, Any]]]
    save_autoreply_pending_item: Callable[[str, dict[str, Any]], None]
    clear_autoreply_pending: Callable[[str], None]
    load_processed_inbound_messages: Callable[[], dict[str, str]]
    mark_processed_inbound_message: Callable[[dict[str, str], str, dict[str, Any]], None]
    load_manager_telegram_notified_message_keys: Callable[[], dict[str, set[str]]]
    mark_manager_telegram_notified_message: Callable[[dict[str, set[str]], str, dict[str, Any]], None]
    load_qualified_buying_chat_ids: Callable[[], set[str]]
    add_qualified_buying_chat_id: Callable[[str], None]
    clear_automatic_takeover_for_qualified_chats: Callable[[set[str]], None]
    manager_takeover_chat_ids: set[str]
    persist_avito_chats: Callable[[list[dict[str, Any]]], None]
    persist_avito_messages: Callable[[str, dict[str, Any]], None]
    track_bot_control_items: Callable[[list[dict[str, Any]]], None]
    notify_manager_handoff: Callable[..., Any]
    notify_manager_folder_messages: Callable[..., Any]
    latest_non_system_message: Callable[[dict[str, Any]], dict[str, Any] | None]
    is_recent_chat: Callable[[dict[str, Any]], bool]
    message_processing_key: Callable[[dict[str, Any]], str]
    has_outbound_after_message: Callable[[dict[str, Any], dict[str, Any] | None], bool]
    estimate_reply_seconds: Callable[[dict[str, Any]], int]
    elapsed_ms: Callable[[float, float | None], int]


async def process_unread(limit: int, services: ProcessUnreadServices) -> dict[str, Any]:
    results: list[ProcessedUnreadChat] = []
    pending = services.load_autoreply_pending()
    processed_inbound = services.load_processed_inbound_messages()
    manager_notified_messages = services.load_manager_telegram_notified_message_keys()
    qualified_chat_ids = services.load_qualified_buying_chat_ids()
    services.clear_automatic_takeover_for_qualified_chats(qualified_chat_ids)
    scan_started_at = time.time()
    services.record_admin_log("info", "chat_scan_start", {"limit": limit, "pending_count": len(pending)})

    try:
        chats_response = await services.avito.get_chats(limit=limit, unread_only=True)
    except Exception as exc:
        services.record_admin_log(
            "error",
            "chat_scan_failed",
            {"stage": "unread_chats", "error": services.error_detail(exc)},
        )
        raise services.to_http_error(exc) from exc

    chats = list(chats_response.get("chats", []))
    seen_chat_ids = {str(chat.get("id") or "") for chat in chats}
    try:
        recent_response = await services.avito.get_chats(limit=limit, unread_only=False)
    except Exception as exc:
        services.record_admin_log(
            "error",
            "chat_scan_failed",
            {"stage": "recent_chats", "error": services.error_detail(exc)},
        )
        raise services.to_http_error(exc) from exc
    for chat in recent_response.get("chats", []):
        chat_id = str(chat.get("id") or "")
        if not chat_id or chat_id in seen_chat_ids:
            continue
        if services.is_recent_chat(chat):
            chats.append(chat)
            seen_chat_ids.add(chat_id)

    for chat_id in list(pending):
        if chat_id and chat_id not in seen_chat_ids:
            try:
                chat = await services.avito.get_chat(chat_id)
                chat.setdefault("id", chat_id)
                chats.append(chat)
            except Exception as exc:
                services.record_admin_log(
                    "warning",
                    "pending_chat_restore_failed",
                    {"chat_id": chat_id, "error": services.error_detail(exc)},
                )
                chats.append({"id": chat_id})

    services.persist_avito_chats(chats)
    services.track_bot_control_items(chats)

    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            services.record_admin_log("warning", "chat_skipped", {"reason": "missing_chat_id"})
            results.append(ProcessedUnreadChat(chat_id="", status="skipped", error="missing chat id"))
            continue

        try:
            await _process_chat(chat, chat_id, pending, processed_inbound, manager_notified_messages, qualified_chat_ids, results, services)
        except Exception as exc:
            services.record_admin_log(
                "error",
                "chat_processing_failed",
                {"chat_id": chat_id, "error": services.error_detail(exc)},
            )
            results.append(ProcessedUnreadChat(chat_id=chat_id, status="failed", error=services.error_detail(exc)))

    services.record_admin_log(
        "info",
        "chat_scan_end",
        {
            "processed_count": len(results),
            "sent_count": sum(1 for result in results if result.status == "sent"),
            "handoff_count": sum(1 for result in results if result.handoff_required),
            "duration_ms": services.elapsed_ms(scan_started_at, None),
        },
    )
    return {
        "processed": [result.model_dump() for result in results],
        "processed_count": len(results),
        "sent_count": sum(1 for result in results if result.status == "sent"),
        "handoff_count": sum(1 for result in results if result.handoff_required),
    }


async def _process_chat(
    chat: dict[str, Any],
    chat_id: str,
    pending: dict[str, dict[str, Any]],
    processed_inbound: dict[str, str],
    manager_notified_messages: dict[str, set[str]],
    qualified_chat_ids: set[str],
    results: list[ProcessedUnreadChat],
    services: ProcessUnreadServices,
) -> None:
    messages = await services.avito.get_messages(chat_id, limit=30)
    services.persist_avito_messages(chat_id, messages)
    latest_message = services.latest_non_system_message(messages)
    pending_item = pending.get(chat_id)
    is_manager_takeover = chat_id in services.manager_takeover_chat_ids
    is_qualified_buying = chat_id in qualified_chat_ids
    pre_strategy = select_pre_draft_strategy(
        manager_takeover=is_manager_takeover,
        latest_message_is_inbound=bool(latest_message and latest_message.get("direction") == "in"),
        already_processed=False,
    )
    if is_manager_takeover or is_qualified_buying:
        services.record_admin_log(
            "info",
            "chat_manager_folder",
            {
                "chat_id": chat_id,
                "manager_takeover": is_manager_takeover,
                "qualified_buying": is_qualified_buying,
                "reply_strategy": pre_strategy.strategy.value,
                "strategy_reason": pre_strategy.reason,
            },
        )
        manager_notification = await services.notify_manager_folder_messages(
            services.settings,
            chat=chat,
            chat_id=chat_id,
            messages_response=messages,
            notified_state=manager_notified_messages,
        )
        if is_manager_takeover:
            if pending_item:
                services.clear_autoreply_pending(chat_id)
            status = "manager_notified" if manager_notification["notified_count"] else "manager_active"
            results.append(
                ProcessedUnreadChat(
                    chat_id=chat_id,
                    status=status,
                    error=manager_notification["errors"] or None,
                )
            )
            return

    if not latest_message or latest_message.get("direction") != "in":
        pre_strategy = select_pre_draft_strategy(
            manager_takeover=False,
            latest_message_is_inbound=False,
            already_processed=False,
        )
        status = "answered" if services.has_outbound_after_message(messages, pending_item) else "skipped"
        services.clear_autoreply_pending(chat_id)
        services.record_admin_log(
            "info",
            "chat_skipped",
            {
                "chat_id": chat_id,
                "reason": "no_latest_inbound",
                "status": status,
                "reply_strategy": pre_strategy.strategy.value,
                "strategy_reason": pre_strategy.reason,
            },
        )
        results.append(ProcessedUnreadChat(chat_id=chat_id, status=status))
        return

    message_key = services.message_processing_key(latest_message)
    if not pending_item and processed_inbound.get(chat_id) == message_key:
        pre_strategy = select_pre_draft_strategy(
            manager_takeover=False,
            latest_message_is_inbound=True,
            already_processed=True,
        )
        services.record_admin_log(
            "info",
            "chat_skipped",
            {
                "chat_id": chat_id,
                "reason": "already_processed",
                "message_key": message_key,
                "reply_strategy": pre_strategy.strategy.value,
                "strategy_reason": pre_strategy.reason,
            },
        )
        results.append(ProcessedUnreadChat(chat_id=chat_id, status="already_processed"))
        return

    received_message_id = str(latest_message.get("id") or "")
    if pending_item and pending_item.get("message_id") == received_message_id:
        accepted_at = float(pending_item.get("accepted_at") or time.time())
        estimate_seconds = int(pending_item.get("estimate_seconds") or services.estimate_reply_seconds(latest_message))
    else:
        accepted_at = time.time()
        estimate_seconds = services.estimate_reply_seconds(latest_message)
        item = {
            "chat_id": chat_id,
            "message_id": received_message_id,
            "accepted_at": accepted_at,
            "estimate_seconds": estimate_seconds,
        }
        services.save_autoreply_pending_item(chat_id, item)
        pending[chat_id] = item
        await services.avito.mark_chat_read(chat_id)
        services.record_admin_log(
            "info",
            "message_accepted",
            {
                "chat_id": chat_id,
                "message_id": received_message_id,
                "estimate_seconds": estimate_seconds,
            },
        )
    draft = await services.assistant.draft_reply(chat, messages)
    post_strategy = select_post_draft_strategy(handoff_required=draft.handoff_required)
    services.record_admin_log(
        "info",
        "ai_draft_decision",
        {
            "chat_id": chat_id,
            "message_id": received_message_id,
            "reply_strategy": post_strategy.strategy.value,
            "strategy_reason": post_strategy.reason,
            "handoff_required": draft.handoff_required,
            "handoff_reason": draft.handoff_reason,
            "reply_length": len(draft.text.strip()),
        },
    )
    if draft.handoff_required:
        await _send_handoff_reply(
            chat,
            chat_id,
            latest_message,
            received_message_id,
            accepted_at,
            estimate_seconds,
            draft,
            post_strategy.strategy.value,
            processed_inbound,
            manager_notified_messages,
            results,
            services,
        )
        return

    sent = await services.avito.send_text_message(chat_id, draft.text.strip())
    services.get_runtime_store().record_manager_action(
        chat_id,
        "ai_auto_reply_sent",
        {"text": draft.text.strip(), "reply_strategy": post_strategy.strategy.value, "avito_response": sent},
    )
    services.mark_processed_inbound_message(processed_inbound, chat_id, latest_message)
    sent_at = time.time()
    services.clear_autoreply_pending(chat_id)
    services.record_admin_log(
        "info",
        "ai_auto_reply_sent",
        {
            "chat_id": chat_id,
            "message_id": received_message_id,
            "sent_message_id": str(sent.get("id") or ""),
            "reply_strategy": post_strategy.strategy.value,
            "strategy_reason": post_strategy.reason,
            "duration_ms": services.elapsed_ms(accepted_at, sent_at),
        },
    )
    results.append(
        ProcessedUnreadChat(
            chat_id=chat_id,
            status="sent",
            received_message_id=received_message_id,
            accepted_at=accepted_at,
            estimate_seconds=estimate_seconds,
            estimated_reply_at=accepted_at + estimate_seconds,
            sent_at=sent_at,
            duration_ms=services.elapsed_ms(accepted_at, sent_at),
            sent_message_id=str(sent.get("id") or ""),
        )
    )


async def _send_handoff_reply(
    chat: dict[str, Any],
    chat_id: str,
    latest_message: dict[str, Any],
    received_message_id: str,
    accepted_at: float,
    estimate_seconds: int,
    draft: Any,
    reply_strategy: str,
    processed_inbound: dict[str, str],
    manager_notified_messages: dict[str, set[str]],
    results: list[ProcessedUnreadChat],
    services: ProcessUnreadServices,
) -> None:
    sent = await services.avito.send_text_message(chat_id, draft.text.strip())
    sent_at = time.time()
    services.mark_processed_inbound_message(processed_inbound, chat_id, latest_message)
    services.add_qualified_buying_chat_id(chat_id)
    notification = await services.notify_manager_handoff(
        services.settings,
        chat=chat,
        chat_id=chat_id,
        handoff_reason=draft.handoff_reason,
        received_text=message_text(latest_message),
    )
    services.record_admin_log(
        "info",
        "handoff_detected",
        {
            "chat_id": chat_id,
            "message_id": received_message_id,
            "handoff_reason": draft.handoff_reason,
            "notification_status": notification.get("status"),
        },
    )
    if notification.get("status") != "failed":
        services.mark_manager_telegram_notified_message(manager_notified_messages, chat_id, latest_message)
    services.get_runtime_store().record_manager_action(
        chat_id,
        "handoff_required",
        {
            "handoff_reason": draft.handoff_reason,
            "received_message_id": received_message_id,
            "received_text": message_text(latest_message),
            "handoff_reply_text": draft.text.strip(),
            "reply_strategy": reply_strategy,
            "avito_response": sent,
            "manager_notification": notification,
        },
    )
    services.clear_autoreply_pending(chat_id)
    results.append(
        ProcessedUnreadChat(
            chat_id=chat_id,
            status="handoff_required",
            handoff_required=True,
            handoff_reason=draft.handoff_reason,
            received_message_id=received_message_id,
            accepted_at=accepted_at,
            estimate_seconds=estimate_seconds,
            estimated_reply_at=accepted_at + estimate_seconds,
            sent_at=sent_at,
            duration_ms=services.elapsed_ms(accepted_at, sent_at),
            sent_message_id=str(sent.get("id") or ""),
        )
    )
