from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ai_client import FallbackAIClient
from app import autoreply_logic
from app.assistant import SalesAssistant, order_messages
from app.avito_payload import chat_item_key, message_text, safe_int
from app.avito_client import AvitoClient, AvitoConfigError
from app.bot_rules import has_buying_intent
from app.codex_app_server_client import CodexAppServerClient, CodexAppServerConfigError
from app.config import get_settings
from app.config import Settings
from app.deepseek_client import DeepSeekClient, DeepSeekConfigError
from app import manager_notifications, runtime_state
from app.storage import RuntimeStore


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "app" / "static"
RUNTIME_DIR = ROOT / ".codex-runtime"
AUTOREPLY_PENDING_PATH = RUNTIME_DIR / "autoreply-pending.json"
AUTOREPLY_STATE_PATH = RUNTIME_DIR / "autoreply-state.json"
BOT_CONTROL_STATE_PATH = RUNTIME_DIR / "bot-control-state.json"
QUALIFIED_BUYING_STATE_KEY = "qualified_buying_chat_ids"
PROCESSED_INBOUND_STATE_KEY = "processed_inbound_message_keys"
MANAGER_TELEGRAM_NOTIFIED_STATE_KEY = "manager_telegram_notified_message_keys"
RECENT_READ_CHAT_LOOKBACK_SECONDS = 15 * 60

webhook_events: list[dict[str, Any]] = []
manager_takeover_chat_ids: set[str] = set()
explicit_manager_takeover_chat_ids: set[str] = set()
known_bot_control_chat_ids: set[str] = set()
known_bot_control_item_keys: set[str] = set()
bot_control_state_loaded = False
process_unread_lock = asyncio.Lock()
bot_worker_task: asyncio.Task[None] | None = None
backup_worker_task: asyncio.Task[None] | None = None
bot_worker_enabled = False
bot_worker_interval_seconds = 5
runtime_store: RuntimeStore | None = None
runtime_store_key: tuple[str, str, str] | None = None
admin_log_sequence = 0
admin_logs: deque[dict[str, Any]] = deque(maxlen=300)
bot_activity: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "interval_seconds": bot_worker_interval_seconds,
    "last_started_at": None,
    "last_finished_at": None,
    "last_result": None,
    "last_error": None,
}


async def _restore_bot_worker_state() -> None:
    global bot_worker_enabled, bot_worker_task
    if not _load_autoreply_enabled():
        return
    settings = get_settings()
    if not settings.avito_live_sync_enabled:
        _save_autoreply_enabled(False)
        bot_activity["last_error"] = "Avito live sync is disabled"
        return
    if not settings.has_avito_credentials:
        bot_activity["last_error"] = "AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required"
        return
    bot_worker_enabled = True
    bot_activity.update(
        {
            "enabled": True,
            "interval_seconds": bot_worker_interval_seconds,
            "last_error": None,
        }
    )
    if bot_worker_task is None or bot_worker_task.done():
        bot_worker_task = asyncio.create_task(_bot_worker_loop())


@asynccontextmanager
async def lifespan(application: FastAPI):
    global backup_worker_task
    get_runtime_store().ensure_schema()
    _migrate_legacy_runtime_json_to_store()
    await _restore_bot_worker_state()
    backup_worker_task = asyncio.create_task(_backup_worker_loop())
    try:
        yield
    finally:
        if backup_worker_task is not None:
            backup_worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await backup_worker_task


app = FastAPI(title="avito-bot", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class DraftReplyRequest(BaseModel):
    chat: dict[str, Any] = Field(default_factory=dict)
    messages: dict[str, Any] = Field(default_factory=dict)


class ChatBotControlRequest(BaseModel):
    manager_takeover: bool


class QualifiedBuyingChatsRequest(BaseModel):
    chat_ids: list[str] = Field(default_factory=list)


class ItemStatsRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=200)
    date_from: date
    date_to: date
    period_grouping: str = Field(default="day", pattern="^(day|week|month)$")
    fields: list[str] = Field(default_factory=lambda: ["uniqViews", "uniqContacts", "uniqFavorites"])


class ProcessedUnreadChat(BaseModel):
    chat_id: str
    status: str
    handoff_required: bool = False
    handoff_reason: str | None = None
    received_message_id: str | None = None
    accepted_at: float | None = None
    estimate_seconds: int | None = None
    estimated_reply_at: float | None = None
    sent_at: float | None = None
    duration_ms: int | None = None
    sent_message_id: str | None = None
    error: object | None = None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config/status")
async def config_status() -> dict[str, object]:
    return get_settings().public_status()


@app.get("/api/storage/status")
async def storage_status() -> dict[str, object]:
    return {
        **get_runtime_store().status(),
        "backup_interval_seconds": get_settings().backup_interval_seconds,
        "backup_retention_count": get_settings().backup_retention_count,
    }


@app.get("/api/admin/logs")
async def admin_logs_endpoint(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 300))
    records = list(admin_logs)[-limit:]
    return {"logs": records, "count": len(records), "max_count": admin_logs.maxlen}


@app.post("/api/storage/backup")
async def storage_backup() -> dict[str, object]:
    result = get_runtime_store().create_backup(keep=get_settings().backup_retention_count)
    return {
        "ok": True,
        "backend": result.backend,
        "path": str(result.path),
        "bytes": result.bytes,
        "created_at": result.created_at,
    }


@app.post("/api/ai/ping")
async def ai_ping() -> dict[str, object]:
    settings = get_settings()
    client = create_ai_client(settings)
    try:
        reply = await client.ping()
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {"ok": reply.lower() == "ok", "provider": settings.ai_provider, "reply": reply}


@app.post("/api/ai/draft-reply")
async def ai_draft_reply(request: DraftReplyRequest) -> dict[str, Any]:
    settings = get_settings()
    assistant = SalesAssistant(create_ai_client(settings))
    try:
        draft = await assistant.draft_reply(request.chat, request.messages)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {
        "text": draft.text,
        "handoff_required": draft.handoff_required,
        "handoff_reason": draft.handoff_reason,
    }


@app.post("/api/avito/token-check")
async def avito_token_check() -> dict[str, object]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        token = await client.get_access_token()
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {
        "ok": True,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
    }


@app.get("/api/avito/account")
async def avito_account() -> dict[str, Any]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        return await client.get_account_self()
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.get("/api/avito/chats")
async def avito_chats(
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    refresh: bool = True,
) -> dict[str, Any]:
    if not refresh or not get_settings().avito_live_sync_enabled:
        chats = get_runtime_store().list_avito_chats(limit=limit, offset=offset, unread_only=unread_only)
        _track_bot_control_items(chats)
        return {
            "chats": chats,
            "source": "cache",
            "qualified_buying_chat_ids": sorted(_load_qualified_buying_chat_ids()),
        }
    client = AvitoClient(get_settings())
    try:
        response = await client.get_chats(limit=limit, offset=offset, unread_only=unread_only)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    chats = list(response.get("chats", []))
    _persist_avito_chats(chats)
    _track_bot_control_items(chats)
    response["qualified_buying_chat_ids"] = await _sync_qualified_buying_from_chats(client, chats)
    return response


@app.get("/api/avito/chats/{chat_id}")
async def avito_chat(chat_id: str, refresh: bool = True) -> dict[str, Any]:
    if not refresh or not get_settings().avito_live_sync_enabled:
        cached = get_runtime_store().get_avito_chat(chat_id)
        if cached is not None:
            return {**cached, "source": "cache"}
        raise HTTPException(status_code=404, detail="Chat is not available in PostgreSQL cache")
    client = AvitoClient(get_settings())
    try:
        response = await client.get_chat(chat_id)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    _persist_avito_chats([{**response, "id": response.get("id") or chat_id}])
    return response


@app.get("/api/avito/chats/{chat_id}/messages")
async def avito_messages(chat_id: str, limit: int = 50, offset: int = 0, refresh: bool = True) -> dict[str, Any]:
    if not refresh or not get_settings().avito_live_sync_enabled:
        messages = get_runtime_store().list_avito_messages(chat_id, limit=limit, offset=offset)
        if messages:
            return {"messages": messages, "source": "cache"}
        return {"messages": [], "source": "cache"}
    client = AvitoClient(get_settings())
    try:
        response = await client.get_messages(chat_id, limit=limit, offset=offset)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    _persist_avito_messages(chat_id, response)
    return response


@app.post("/api/avito/chats/{chat_id}/messages")
async def avito_send_message(chat_id: str, request: SendMessageRequest) -> dict[str, Any]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        response = await client.send_text_message(chat_id, request.text)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    get_runtime_store().record_manager_action(
        chat_id,
        "send_message",
        {"text": request.text, "avito_response": response},
    )
    return response


@app.post("/api/avito/chats/{chat_id}/read")
async def avito_mark_read(chat_id: str) -> dict[str, Any]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        return await client.mark_chat_read(chat_id)
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.post("/api/avito/item-stats")
async def avito_item_stats(request: ItemStatsRequest) -> dict[str, Any]:
    if request.date_to < request.date_from:
        raise HTTPException(status_code=400, detail="date_to must be greater than or equal to date_from")
    client = AvitoClient(get_settings())
    try:
        return await client.get_item_stats(
            item_ids=request.item_ids,
            date_from=request.date_from.isoformat(),
            date_to=request.date_to.isoformat(),
            period_grouping=request.period_grouping,
            fields=request.fields,
        )
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.get("/api/avito/chats/{chat_id}/bot-control")
async def avito_chat_bot_control(chat_id: str) -> dict[str, Any]:
    return _chat_bot_control_response(chat_id)


@app.post("/api/avito/chats/{chat_id}/bot-control")
async def avito_set_chat_bot_control(chat_id: str, request: ChatBotControlRequest) -> dict[str, Any]:
    _ensure_bot_control_state_loaded()
    known_bot_control_chat_ids.add(chat_id)
    if request.manager_takeover:
        manager_takeover_chat_ids.add(chat_id)
        explicit_manager_takeover_chat_ids.add(chat_id)
    else:
        manager_takeover_chat_ids.discard(chat_id)
        explicit_manager_takeover_chat_ids.discard(chat_id)
    _save_bot_control_state()
    get_runtime_store().record_manager_action(
        chat_id,
        "set_bot_control",
        {"manager_takeover": request.manager_takeover},
    )
    return _chat_bot_control_response(chat_id)


@app.get("/api/avito/qualified-buying-chats")
async def avito_qualified_buying_chats() -> dict[str, Any]:
    chat_ids = _load_qualified_buying_chat_ids()
    _clear_automatic_takeover_for_qualified_chats(chat_ids)
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@app.post("/api/avito/qualified-buying-chats")
async def avito_save_qualified_buying_chats(request: QualifiedBuyingChatsRequest) -> dict[str, Any]:
    chat_ids = _load_qualified_buying_chat_ids()
    new_chat_ids = _normalize_chat_ids(request.chat_ids)
    chat_ids.update(new_chat_ids)
    _save_qualified_buying_chat_ids(chat_ids)
    _clear_automatic_takeover_for_qualified_chats(new_chat_ids)
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@app.post("/api/avito/chats/{chat_id}/ai-draft")
async def avito_ai_draft(chat_id: str) -> dict[str, Any]:
    settings = get_settings()
    assistant = SalesAssistant(create_ai_client(settings))
    try:
        if settings.avito_live_sync_enabled:
            avito = AvitoClient(settings)
            chat = await avito.get_chat(chat_id)
            messages = await avito.get_messages(chat_id, limit=30)
        else:
            chat = get_runtime_store().get_avito_chat(chat_id) or {"id": chat_id}
            messages = {"messages": get_runtime_store().list_avito_messages(chat_id, limit=30)}
        draft = await assistant.draft_reply(chat, messages)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {
        "text": draft.text,
        "handoff_required": draft.handoff_required,
        "handoff_reason": draft.handoff_reason,
    }


@app.post("/api/avito/process-unread")
async def avito_process_unread(limit: int = 20) -> dict[str, Any]:
    _require_avito_live_sync()
    async with process_unread_lock:
        return await _process_unread(limit=limit)


@app.post("/api/bot/autoreply/start")
async def bot_autoreply_start() -> dict[str, Any]:
    global bot_worker_enabled, bot_worker_task
    settings = get_settings()
    _require_avito_live_sync(settings)
    if not settings.has_avito_credentials:
        raise HTTPException(status_code=400, detail="AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required")
    bot_worker_enabled = True
    _record_admin_log("info", "autoreply_start", {"interval_seconds": bot_worker_interval_seconds})
    bot_activity.update(
        {
            "enabled": True,
            "interval_seconds": bot_worker_interval_seconds,
            "last_error": None,
        }
    )
    _save_autoreply_enabled(True)
    if bot_worker_task is None or bot_worker_task.done():
        bot_worker_task = asyncio.create_task(_bot_worker_loop())
    return _bot_activity_response()


@app.post("/api/bot/autoreply/stop")
async def bot_autoreply_stop() -> dict[str, Any]:
    global bot_worker_enabled
    bot_worker_enabled = False
    bot_activity["enabled"] = False
    _record_admin_log("info", "autoreply_stop")
    _save_autoreply_enabled(False)
    return _bot_activity_response()


@app.get("/api/bot/autoreply/status")
async def bot_autoreply_status() -> dict[str, Any]:
    return _bot_activity_response()


async def _process_unread(limit: int = 20) -> dict[str, Any]:
    settings = get_settings()
    avito = AvitoClient(settings)
    assistant = SalesAssistant(create_ai_client(settings))
    results: list[ProcessedUnreadChat] = []
    pending = _load_autoreply_pending()
    processed_inbound = _load_processed_inbound_messages()
    manager_notified_messages = _load_manager_telegram_notified_message_keys()
    qualified_chat_ids = _load_qualified_buying_chat_ids()
    _clear_automatic_takeover_for_qualified_chats(qualified_chat_ids)
    scan_started_at = time.time()

    try:
        chats_response = await avito.get_chats(limit=limit, unread_only=True)
    except Exception as exc:
        raise _to_http_error(exc) from exc

    chats = list(chats_response.get("chats", []))
    seen_chat_ids = {str(chat.get("id") or "") for chat in chats}
    try:
        recent_response = await avito.get_chats(limit=limit, unread_only=False)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    for chat in recent_response.get("chats", []):
        chat_id = str(chat.get("id") or "")
        if not chat_id or chat_id in seen_chat_ids:
            continue
        if _is_recent_chat(chat, now=scan_started_at):
            chats.append(chat)
            seen_chat_ids.add(chat_id)

    for chat_id in list(pending):
        if chat_id and chat_id not in seen_chat_ids:
            try:
                chat = await avito.get_chat(chat_id)
                chat.setdefault("id", chat_id)
                chats.append(chat)
            except Exception:
                chats.append({"id": chat_id})

    _persist_avito_chats(chats)
    _track_bot_control_items(chats)

    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            results.append(ProcessedUnreadChat(chat_id="", status="skipped", error="missing chat id"))
            continue

        try:
            messages = await avito.get_messages(chat_id, limit=30)
            _persist_avito_messages(chat_id, messages)
            latest_message = _latest_non_system_message(messages)
            pending_item = pending.get(chat_id)
            is_manager_takeover = chat_id in manager_takeover_chat_ids
            is_qualified_buying = chat_id in qualified_chat_ids
            if is_manager_takeover or is_qualified_buying:
                manager_notification = await _notify_manager_folder_messages(
                    settings,
                    chat=chat,
                    chat_id=chat_id,
                    messages_response=messages,
                    notified_state=manager_notified_messages,
                )
                if is_manager_takeover:
                    if pending_item:
                        _clear_autoreply_pending(chat_id)
                    status = "manager_notified" if manager_notification["notified_count"] else "manager_active"
                    results.append(
                        ProcessedUnreadChat(
                            chat_id=chat_id,
                            status=status,
                            error=manager_notification["errors"] or None,
                        )
                    )
                    continue

            if not latest_message or latest_message.get("direction") != "in":
                status = "answered" if _has_outbound_after_message(messages, pending_item) else "skipped"
                _clear_autoreply_pending(chat_id)
                results.append(ProcessedUnreadChat(chat_id=chat_id, status=status))
                continue

            message_key = _message_processing_key(latest_message)
            if not pending_item and processed_inbound.get(chat_id) == message_key:
                results.append(ProcessedUnreadChat(chat_id=chat_id, status="already_processed"))
                continue

            received_message_id = str(latest_message.get("id") or "")
            if pending_item and pending_item.get("message_id") == received_message_id:
                accepted_at = float(pending_item.get("accepted_at") or time.time())
                estimate_seconds = int(pending_item.get("estimate_seconds") or _estimate_reply_seconds(latest_message))
            else:
                accepted_at = time.time()
                estimate_seconds = _estimate_reply_seconds(latest_message)
                _save_autoreply_pending_item(
                    chat_id,
                    {
                        "chat_id": chat_id,
                        "message_id": received_message_id,
                        "accepted_at": accepted_at,
                        "estimate_seconds": estimate_seconds,
                    },
                )
                pending[chat_id] = {
                    "chat_id": chat_id,
                    "message_id": received_message_id,
                    "accepted_at": accepted_at,
                    "estimate_seconds": estimate_seconds,
                }
                await avito.mark_chat_read(chat_id)
            draft = await assistant.draft_reply(chat, messages)
            if draft.handoff_required:
                sent = await avito.send_text_message(chat_id, draft.text.strip())
                sent_at = time.time()
                _mark_processed_inbound_message(processed_inbound, chat_id, latest_message)
                _add_qualified_buying_chat_id(chat_id)
                notification = await _notify_manager_handoff(
                    settings,
                    chat=chat,
                    chat_id=chat_id,
                    handoff_reason=draft.handoff_reason,
                    received_text=message_text(latest_message),
                )
                if notification.get("status") != "failed":
                    _mark_manager_telegram_notified_message(manager_notified_messages, chat_id, latest_message)
                get_runtime_store().record_manager_action(
                    chat_id,
                    "handoff_required",
                    {
                        "handoff_reason": draft.handoff_reason,
                        "received_message_id": received_message_id,
                        "received_text": message_text(latest_message),
                        "handoff_reply_text": draft.text.strip(),
                        "avito_response": sent,
                        "manager_notification": notification,
                    },
                )
                _clear_autoreply_pending(chat_id)
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
                        duration_ms=_elapsed_ms(accepted_at, sent_at),
                        sent_message_id=str(sent.get("id") or ""),
                    )
                )
                continue

            sent = await avito.send_text_message(chat_id, draft.text.strip())
            get_runtime_store().record_manager_action(
                chat_id,
                "ai_auto_reply_sent",
                {"text": draft.text.strip(), "avito_response": sent},
            )
            _mark_processed_inbound_message(processed_inbound, chat_id, latest_message)
            sent_at = time.time()
            _clear_autoreply_pending(chat_id)
            results.append(
                ProcessedUnreadChat(
                    chat_id=chat_id,
                    status="sent",
                    received_message_id=received_message_id,
                    accepted_at=accepted_at,
                    estimate_seconds=estimate_seconds,
                    estimated_reply_at=accepted_at + estimate_seconds,
                    sent_at=sent_at,
                    duration_ms=_elapsed_ms(accepted_at, sent_at),
                    sent_message_id=str(sent.get("id") or ""),
                )
            )
        except Exception as exc:
            results.append(ProcessedUnreadChat(chat_id=chat_id, status="failed", error=_error_detail(exc)))

    return {
        "processed": [result.model_dump() for result in results],
        "processed_count": len(results),
        "sent_count": sum(1 for result in results if result.status == "sent"),
        "handoff_count": sum(1 for result in results if result.handoff_required),
    }


async def _bot_worker_loop() -> None:
    global bot_worker_enabled
    while bot_worker_enabled:
        started_at = time.time()
        bot_activity.update(
            {
                "enabled": True,
                "running": True,
                "last_started_at": started_at,
                "last_error": None,
            }
        )
        try:
            async with process_unread_lock:
                result = await _process_unread(limit=20)
            bot_activity["last_result"] = result
        except Exception as exc:  # pragma: no cover - surfaced through status endpoint
            bot_activity["last_error"] = _error_detail(exc)
        finally:
            bot_activity.update(
                {
                    "running": False,
                    "last_finished_at": time.time(),
                    "enabled": bot_worker_enabled,
                }
            )
        await asyncio.sleep(bot_worker_interval_seconds)


def _bot_activity_response() -> dict[str, Any]:
    task_state = "stopped"
    if bot_worker_task is not None and not bot_worker_task.done():
        task_state = "running" if bot_activity["running"] else "waiting"
    return {
        **bot_activity,
        "task_state": task_state,
    }


def _chat_bot_control_response(chat_id: str) -> dict[str, Any]:
    _ensure_bot_control_state_loaded()
    manager_takeover = chat_id in manager_takeover_chat_ids
    return {
        "chat_id": chat_id,
        "manager_takeover": manager_takeover,
        "bot_enabled": not manager_takeover,
    }


@app.post("/webhooks/avito/messenger")
async def avito_webhook(payload: dict[str, Any]) -> dict[str, object]:
    webhook_events.insert(0, payload)
    del webhook_events[50:]
    get_runtime_store().record_manager_action(
        str(payload.get("chat_id") or payload.get("id") or "webhook"),
        "webhook_received",
        payload,
    )
    return {"ok": True}


@app.get("/api/webhooks/avito/events")
async def avito_webhook_events() -> dict[str, Any]:
    return {"events": webhook_events}


def get_runtime_store() -> RuntimeStore:
    global runtime_store, runtime_store_key
    candidate = RuntimeStore.from_settings(get_settings(), root=ROOT, runtime_dir=RUNTIME_DIR)
    candidate_key = candidate.cache_key()
    if runtime_store is None or runtime_store_key != candidate_key:
        runtime_store = candidate
        runtime_store_key = candidate_key
        runtime_store.ensure_schema()
    return runtime_store


async def _backup_worker_loop() -> None:
    while True:
        await asyncio.sleep(get_settings().backup_interval_seconds)
        try:
            store = get_runtime_store()
            store.create_backup(keep=get_settings().backup_retention_count)
        except Exception as exc:  # pragma: no cover - surfaced through storage status/logs
            bot_activity["last_backup_error"] = _error_detail(exc)


def _migrate_legacy_runtime_json_to_store() -> None:
    store = get_runtime_store()
    if store.get_state("autoreply_pending") is None and AUTOREPLY_PENDING_PATH.exists():
        pending = _load_json_file(AUTOREPLY_PENDING_PATH, default={})
        if isinstance(pending, dict):
            store.set_state("autoreply_pending", pending)
    if store.get_state("autoreply_enabled") is None and AUTOREPLY_STATE_PATH.exists():
        state = _load_json_file(AUTOREPLY_STATE_PATH, default={})
        if isinstance(state, dict):
            store.set_state("autoreply_enabled", bool(state.get("enabled") is True))
    if store.get_state("bot_control") is None and BOT_CONTROL_STATE_PATH.exists():
        state = _load_json_file(BOT_CONTROL_STATE_PATH, default={})
        if isinstance(state, dict):
            store.set_state("bot_control", state)


def _require_avito_live_sync(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.avito_live_sync_enabled:
        _record_admin_log("warning", "live_sync_blocked", {"reason": "AVITO_LIVE_SYNC_ENABLED=false"})
        raise HTTPException(status_code=409, detail="Avito live sync is disabled; using PostgreSQL cache only")


def _load_json_file(path: Path, *, default: Any) -> Any:
    return runtime_state.load_json_file(path, default=default)


def _persist_avito_chats(chats: list[dict[str, Any]]) -> None:
    try:
        get_runtime_store().upsert_avito_chats(chats)
    except Exception:
        pass


def _persist_avito_messages(chat_id: str, messages_response: dict[str, Any]) -> None:
    messages = list(messages_response.get("messages", []))
    if not messages:
        return
    try:
        get_runtime_store().upsert_avito_messages(chat_id, messages)
    except Exception:
        pass


def _load_autoreply_pending() -> dict[str, dict[str, Any]]:
    return runtime_state.load_autoreply_pending(get_runtime_store(), AUTOREPLY_PENDING_PATH)


def _write_autoreply_pending(pending: dict[str, dict[str, Any]]) -> None:
    runtime_state.write_autoreply_pending(get_runtime_store(), AUTOREPLY_PENDING_PATH, pending)


def _save_autoreply_pending_item(chat_id: str, item: dict[str, Any]) -> None:
    runtime_state.save_autoreply_pending_item(get_runtime_store(), AUTOREPLY_PENDING_PATH, chat_id, item)


def _clear_autoreply_pending(chat_id: str) -> None:
    runtime_state.clear_autoreply_pending(get_runtime_store(), AUTOREPLY_PENDING_PATH, chat_id)


def _load_autoreply_enabled() -> bool:
    return runtime_state.load_autoreply_enabled(get_runtime_store(), AUTOREPLY_STATE_PATH)


def _save_autoreply_enabled(enabled: bool) -> None:
    runtime_state.save_autoreply_enabled(get_runtime_store(), AUTOREPLY_STATE_PATH, enabled)


def _ensure_bot_control_state_loaded() -> None:
    global bot_control_state_loaded
    if bot_control_state_loaded:
        return
    bot_control_state_loaded = True
    known_chat_ids, known_item_keys, takeover_chat_ids, explicit_takeover_chat_ids = runtime_state.load_bot_control_state(
        get_runtime_store(),
        BOT_CONTROL_STATE_PATH,
    )
    known_bot_control_chat_ids.update(known_chat_ids)
    known_bot_control_item_keys.update(known_item_keys)
    manager_takeover_chat_ids.update(takeover_chat_ids)
    explicit_manager_takeover_chat_ids.update(explicit_takeover_chat_ids)


def _save_bot_control_state() -> None:
    runtime_state.save_bot_control_state(
        get_runtime_store(),
        BOT_CONTROL_STATE_PATH,
        known_chat_ids=known_bot_control_chat_ids,
        known_item_keys=known_bot_control_item_keys,
        manager_takeover_chat_ids=manager_takeover_chat_ids,
        explicit_manager_takeover_chat_ids=explicit_manager_takeover_chat_ids,
    )


def _load_qualified_buying_chat_ids() -> set[str]:
    return runtime_state.load_qualified_buying_chat_ids(get_runtime_store(), QUALIFIED_BUYING_STATE_KEY)


def _save_qualified_buying_chat_ids(chat_ids: set[str]) -> None:
    runtime_state.save_qualified_buying_chat_ids(get_runtime_store(), QUALIFIED_BUYING_STATE_KEY, chat_ids)


def _add_qualified_buying_chat_id(chat_id: str) -> None:
    chat_ids = _load_qualified_buying_chat_ids()
    chat_ids.add(chat_id)
    _save_qualified_buying_chat_ids(chat_ids)
    _clear_automatic_takeover_for_qualified_chats({chat_id})


async def _sync_qualified_buying_from_chats(client: AvitoClient, chats: list[dict[str, Any]]) -> list[str]:
    chat_ids = _load_qualified_buying_chat_ids()
    changed_chat_ids: set[str] = set()
    chats_to_inspect: list[tuple[str, dict[str, Any]]] = []
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id or chat_id in chat_ids:
            continue
        if _chat_summary_has_buying_intent(chat):
            changed_chat_ids.add(chat_id)
            continue
        chats_to_inspect.append((chat_id, chat))

    semaphore = asyncio.Semaphore(5)

    async def inspect_chat_messages(chat_id: str) -> str | None:
        async with semaphore:
            try:
                messages = await client.get_messages(chat_id, limit=50)
            except Exception:
                return None
            _persist_avito_messages(chat_id, messages)
            return chat_id if _messages_have_buying_intent(messages) else None

    if chats_to_inspect:
        inspected_ids = await asyncio.gather(
            *(inspect_chat_messages(chat_id) for chat_id, _chat in chats_to_inspect)
        )
        changed_chat_ids.update(chat_id for chat_id in inspected_ids if chat_id)

    if changed_chat_ids:
        chat_ids.update(changed_chat_ids)
        _save_qualified_buying_chat_ids(chat_ids)
    _clear_automatic_takeover_for_qualified_chats(chat_ids)
    return sorted(chat_ids)


def _clear_automatic_takeover_for_qualified_chats(chat_ids: set[str]) -> None:
    _ensure_bot_control_state_loaded()
    normalized_chat_ids = _normalize_chat_ids(list(chat_ids))
    auto_takeover_chat_ids = (normalized_chat_ids & manager_takeover_chat_ids) - explicit_manager_takeover_chat_ids
    if not auto_takeover_chat_ids:
        return
    manager_takeover_chat_ids.difference_update(auto_takeover_chat_ids)
    _save_bot_control_state()


def _chat_summary_has_buying_intent(chat: dict[str, Any]) -> bool:
    last_message = chat.get("last_message")
    if not isinstance(last_message, dict) or last_message.get("direction") != "in":
        return False
    return _has_buying_intent(message_text(last_message) or "")


def _messages_have_buying_intent(messages_response: dict[str, Any]) -> bool:
    client_texts = [
        message_text(message) or ""
        for message in order_messages(list(messages_response.get("messages", [])))
        if message.get("direction") == "in" and message.get("type") != "system"
    ]
    return _has_buying_intent("\n".join(client_texts))


def _has_buying_intent(text: str) -> bool:
    return has_buying_intent(text)


def _normalize_chat_ids(chat_ids: list[Any]) -> set[str]:
    return runtime_state.normalize_chat_ids(chat_ids)


def _track_bot_control_items(chats: list[dict[str, Any]]) -> None:
    _ensure_bot_control_state_loaded()
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
    if not known_bot_control_item_keys and not BOT_CONTROL_STATE_PATH.exists():
        known_bot_control_item_keys.update(chat_ids_by_item_key)
        known_bot_control_chat_ids.update(
            chat_id for chat_ids in chat_ids_by_item_key.values() for chat_id in chat_ids
        )
        changed = True
    else:
        for item_key, chat_ids in chat_ids_by_item_key.items():
            is_new_item = item_key not in known_bot_control_item_keys
            known_bot_control_item_keys.add(item_key)
            for chat_id in chat_ids:
                if chat_id not in known_bot_control_chat_ids:
                    known_bot_control_chat_ids.add(chat_id)
                    changed = True
            if is_new_item:
                changed = True

    if changed:
        _save_bot_control_state()


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AvitoConfigError, DeepSeekConfigError, CodexAppServerConfigError)):
        _record_admin_log("error", "config_error", {"error": str(exc)})
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        detail: object
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        _record_admin_log(
            "error",
            "avito_http_status_error",
            {"status_code": exc.response.status_code, "detail": _safe_log_detail(detail)},
        )
        return HTTPException(status_code=exc.response.status_code, detail=detail)
    if isinstance(exc, httpx.RequestError):
        _record_admin_log("error", "avito_request_failed", {"error_type": exc.__class__.__name__})
        return HTTPException(status_code=502, detail=f"Avito request failed: {exc.__class__.__name__}")
    return HTTPException(status_code=500, detail=exc.__class__.__name__)


def create_ai_client(settings: Settings) -> DeepSeekClient | CodexAppServerClient | FallbackAIClient:
    provider = settings.ai_provider.strip().lower()
    if provider == "deepseek":
        fallback = CodexAppServerClient(settings) if settings.codex_app_server_base_url else None
        return FallbackAIClient(DeepSeekClient(settings), fallback)
    if provider == "codex_app_server":
        return CodexAppServerClient(settings)
    raise DeepSeekConfigError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")


async def _notify_manager_handoff(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    handoff_reason: str | None,
    received_text: str | None,
) -> dict[str, object]:
    text = _format_manager_telegram_message(
        title="Нужен менеджер",
        chat=chat or {"id": chat_id},
        chat_id=chat_id,
        message_text_value=received_text,
        reason=handoff_reason,
    )
    return await _send_telegram_notification(settings, text)


async def _notify_manager_folder_messages(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    messages_response: dict[str, Any],
    notified_state: dict[str, set[str]],
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
            notified_state[chat_id].add(_message_processing_key(message))
        if inbound_messages[:-1]:
            _save_manager_telegram_notified_message_keys(notified_state)

    for message in inbound_messages:
        message_key = _message_processing_key(message)
        if message_key in notified_state.get(chat_id, set()):
            continue
        text = _format_manager_telegram_message(
            title="Новое сообщение в менеджерской папке",
            chat=chat or {"id": chat_id},
            chat_id=chat_id,
            message_text_value=message_text(message),
            reason=_telegram_reason_for_manager_folder_chat(chat or {}),
        )
        notification = await _send_telegram_notification(settings, text)
        get_runtime_store().record_manager_action(
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
        if notification.get("status") == "skipped":
            _mark_manager_telegram_notified_message(notified_state, chat_id, message)
            continue
        _mark_manager_telegram_notified_message(notified_state, chat_id, message)
        notified_count += 1
    return {"notified_count": notified_count, "errors": errors}


def _format_manager_telegram_message(
    *,
    title: str,
    chat: dict[str, Any],
    chat_id: str,
    message_text_value: str | None,
    reason: str | None,
) -> str:
    return manager_notifications._format_manager_telegram_message(
        title=title,
        chat=chat,
        chat_id=chat_id,
        message_text_value=message_text_value,
        reason=reason,
    )


def _telegram_client_name(chat: dict[str, Any]) -> str:
    return manager_notifications._telegram_client_name(chat)


def _telegram_item_title(chat: dict[str, Any]) -> str:
    return manager_notifications._telegram_item_title(chat)


def _telegram_item_url(chat: dict[str, Any]) -> str:
    return manager_notifications._telegram_item_url(chat)


def _telegram_client_profile_url(chat: dict[str, Any]) -> str:
    return manager_notifications._telegram_client_profile_url(chat)


def _telegram_reason_for_manager_folder_chat(chat: dict[str, Any]) -> str:
    return manager_notifications._telegram_reason_for_manager_folder_chat(chat)


def _manager_local_chat_url(chat_id: str) -> str:
    return manager_notifications._manager_local_chat_url(chat_id)


def _telegram_item_context(chat: dict[str, Any]) -> dict[str, Any]:
    return manager_notifications._telegram_item_context(chat)


def _telegram_chat_users(chat: dict[str, Any]) -> list[dict[str, Any]]:
    return manager_notifications._telegram_chat_users(chat)


def _pick_person_name(person: object) -> str:
    return manager_notifications._pick_person_name(person)


def _clean_text(value: object) -> str:
    return manager_notifications._clean_text(value)


def _string_id(value: object) -> str:
    return manager_notifications._string_id(value)


async def _send_telegram_notification(settings: Settings, text: str) -> dict[str, object]:
    return await manager_notifications._send_telegram_notification(settings, text)


def _latest_non_system_message(messages_response: dict[str, Any]) -> dict[str, Any] | None:
    return autoreply_logic.latest_non_system_message(messages_response)


def _is_recent_chat(chat: dict[str, Any], *, now: float) -> bool:
    return autoreply_logic.is_recent_chat(chat, now=now, lookback_seconds=RECENT_READ_CHAT_LOOKBACK_SECONDS)


def _load_processed_inbound_messages() -> dict[str, str]:
    return runtime_state.load_processed_inbound_messages(get_runtime_store(), PROCESSED_INBOUND_STATE_KEY)


def _load_manager_telegram_notified_message_keys() -> dict[str, set[str]]:
    return runtime_state.load_notified_message_keys(get_runtime_store(), MANAGER_TELEGRAM_NOTIFIED_STATE_KEY)


def _save_manager_telegram_notified_message_keys(state: dict[str, set[str]]) -> None:
    runtime_state.save_notified_message_keys(get_runtime_store(), MANAGER_TELEGRAM_NOTIFIED_STATE_KEY, state)


def _mark_processed_inbound_message(state: dict[str, str], chat_id: str, message: dict[str, Any]) -> None:
    runtime_state.mark_processed_inbound_message(
        get_runtime_store(),
        PROCESSED_INBOUND_STATE_KEY,
        state,
        chat_id,
        _message_processing_key(message),
    )


def _mark_manager_telegram_notified_message(state: dict[str, set[str]], chat_id: str, message: dict[str, Any]) -> None:
    runtime_state.mark_notified_message_key(
        get_runtime_store(),
        MANAGER_TELEGRAM_NOTIFIED_STATE_KEY,
        state,
        chat_id,
        _message_processing_key(message),
    )


def _message_processing_key(message: dict[str, Any]) -> str:
    return autoreply_logic.message_processing_key(message)


def _has_outbound_after_message(messages_response: dict[str, Any], pending_item: dict[str, Any] | None) -> bool:
    return autoreply_logic.has_outbound_after_message(messages_response, pending_item)


def _estimate_reply_seconds(message: dict[str, Any]) -> int:
    return autoreply_logic.estimate_reply_seconds(message)


def _elapsed_ms(started_at: float, finished_at: float | None = None) -> int:
    return autoreply_logic.elapsed_ms(started_at, finished_at)


def _error_detail(exc: Exception) -> object:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json()
        except ValueError:
            return exc.response.text
    return str(exc) or exc.__class__.__name__


def _record_admin_log(level: str, event: str, detail: Any | None = None) -> None:
    global admin_log_sequence
    admin_log_sequence += 1
    admin_logs.append(
        {
            "id": admin_log_sequence,
            "created_at": time.time(),
            "level": level,
            "event": event,
            "detail": _safe_log_detail(detail),
        }
    )


def _safe_log_detail(detail: Any | None) -> Any:
    if detail is None:
        return None
    if isinstance(detail, dict):
        sanitized: dict[str, Any] = {}
        for key, value in detail.items():
            key_text = str(key)
            if any(secret_word in key_text.lower() for secret_word in ("token", "secret", "password", "key")):
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = _safe_log_detail(value)
        return sanitized
    if isinstance(detail, list):
        return [_safe_log_detail(item) for item in detail[:20]]
    if isinstance(detail, (str, int, float, bool)):
        return detail
    return str(detail)
