from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.ai_client import FallbackAIClient
from app import autoreply_logic
from app.admin_logging import AdminLogBuffer, create_runtime_logger, safe_log_detail
from app.assistant import SalesAssistant
from app.avito_client import AvitoClient
from app.bot_rules import has_buying_intent
from app.codex_app_server_client import CodexAppServerClient
from app.config import get_settings
from app.config import Settings
from app.deepseek_client import DeepSeekClient
from app import runtime_state
from app import autoreply_worker, avito_sync, http_errors, manager_notification_service, process_unread, runtime_services
from app.ai_factory import create_ai_client as _create_ai_client
from app.schemas import (
    ChatBotControlRequest,
    DraftReplyRequest,
    ItemStatsRequest,
    QualifiedBuyingChatsRequest,
    SendMessageRequest,
    TelegramNotificationSettingsRequest,
)
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
TELEGRAM_NOTIFICATION_MODE_STATE_KEY = "telegram_notification_mode"
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
bot_worker_interval_seconds = get_settings().autoreply_interval_seconds
runtime_store: RuntimeStore | None = None
runtime_store_key: tuple[str, str, str] | None = None
admin_logs = AdminLogBuffer(maxlen=300)
runtime_logger: object | None = None
runtime_logger_key: tuple[object, ...] | None = None
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
    settings = get_settings()
    await autoreply_worker.restore_worker_state(
        live_sync_enabled=settings.avito_live_sync_enabled,
        has_avito_credentials=settings.has_avito_credentials,
        start_worker=_start_bot_worker_task,
        services=_autoreply_worker_services(),
    )


def _start_bot_worker_task() -> None:
    global bot_worker_task
    if bot_worker_task is None or bot_worker_task.done():
        bot_worker_task = asyncio.create_task(_bot_worker_loop())


def _set_bot_worker_enabled(enabled: bool) -> None:
    global bot_worker_enabled
    bot_worker_enabled = enabled


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

web_router = APIRouter()
health_config_router = APIRouter(prefix="/api")
storage_router = APIRouter(prefix="/api/storage")
ai_router = APIRouter(prefix="/api/ai")
avito_router = APIRouter(prefix="/api/avito")
bot_router = APIRouter(prefix="/api/bot")
webhook_router = APIRouter()


@web_router.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@health_config_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@health_config_router.get("/config/status")
async def config_status() -> dict[str, object]:
    return get_settings().public_status()


@storage_router.get("/status")
async def storage_status() -> dict[str, object]:
    return {
        **get_runtime_store().status(),
        "backup_interval_seconds": get_settings().backup_interval_seconds,
        "backup_retention_count": get_settings().backup_retention_count,
    }


@health_config_router.get("/admin/logs")
async def admin_logs_endpoint(limit: int = 100) -> dict[str, Any]:
    return admin_logs.list(limit=limit)


@storage_router.post("/backup")
async def storage_backup() -> dict[str, object]:
    result = get_runtime_store().create_backup(keep=get_settings().backup_retention_count)
    return {
        "ok": True,
        "backend": result.backend,
        "path": str(result.path),
        "bytes": result.bytes,
        "created_at": result.created_at,
    }


@ai_router.post("/ping")
async def ai_ping() -> dict[str, object]:
    settings = get_settings()
    client = create_ai_client(settings)
    try:
        reply = await client.ping()
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {"ok": reply.lower() == "ok", "provider": settings.ai_provider, "reply": reply}


@ai_router.post("/draft-reply")
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


@avito_router.post("/token-check")
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


@avito_router.get("/account")
async def avito_account() -> dict[str, Any]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        return await client.get_account_self()
    except Exception as exc:
        raise _to_http_error(exc) from exc


@avito_router.get("/chats")
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


@avito_router.get("/chats/{chat_id}")
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


@avito_router.get("/chats/{chat_id}/messages")
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


@avito_router.post("/chats/{chat_id}/messages")
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


@avito_router.post("/chats/{chat_id}/read")
async def avito_mark_read(chat_id: str) -> dict[str, Any]:
    _require_avito_live_sync()
    client = AvitoClient(get_settings())
    try:
        return await client.mark_chat_read(chat_id)
    except Exception as exc:
        raise _to_http_error(exc) from exc


@avito_router.post("/item-stats")
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


@avito_router.get("/chats/{chat_id}/bot-control")
async def avito_chat_bot_control(chat_id: str) -> dict[str, Any]:
    return _chat_bot_control_response(chat_id)


@avito_router.post("/chats/{chat_id}/bot-control")
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
    _record_admin_log(
        "info",
        "manual_takeover_changed",
        {"chat_id": chat_id, "manager_takeover": request.manager_takeover},
    )
    return _chat_bot_control_response(chat_id)


@avito_router.get("/qualified-buying-chats")
async def avito_qualified_buying_chats() -> dict[str, Any]:
    chat_ids = _load_qualified_buying_chat_ids()
    _clear_automatic_takeover_for_qualified_chats(chat_ids)
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@avito_router.post("/qualified-buying-chats")
async def avito_save_qualified_buying_chats(request: QualifiedBuyingChatsRequest) -> dict[str, Any]:
    chat_ids = _load_qualified_buying_chat_ids()
    new_chat_ids = _normalize_chat_ids(request.chat_ids)
    chat_ids.update(new_chat_ids)
    _save_qualified_buying_chat_ids(chat_ids)
    _clear_automatic_takeover_for_qualified_chats(new_chat_ids)
    _record_admin_log(
        "info",
        "qualified_buying_chats_updated",
        {"added_count": len(new_chat_ids), "total_count": len(chat_ids)},
    )
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@avito_router.post("/chats/{chat_id}/ai-draft")
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


@avito_router.post("/process-unread")
async def avito_process_unread(limit: int = 20) -> dict[str, Any]:
    _require_avito_live_sync()
    async with process_unread_lock:
        return await _process_unread(limit=limit)


@bot_router.post("/autoreply/start")
async def bot_autoreply_start() -> dict[str, Any]:
    settings = get_settings()
    _require_avito_live_sync(settings)
    if not settings.has_avito_credentials:
        raise HTTPException(status_code=400, detail="AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required")
    _set_bot_worker_enabled(True)
    _record_admin_log("info", "autoreply_start", {"interval_seconds": bot_worker_interval_seconds})
    bot_activity.update(
        {
            "enabled": True,
            "interval_seconds": bot_worker_interval_seconds,
            "last_error": None,
        }
    )
    _save_autoreply_enabled(True)
    _start_bot_worker_task()
    return _bot_activity_response()


@bot_router.post("/autoreply/stop")
async def bot_autoreply_stop() -> dict[str, Any]:
    _set_bot_worker_enabled(False)
    bot_activity["enabled"] = False
    _record_admin_log("info", "autoreply_stop")
    _save_autoreply_enabled(False)
    return _bot_activity_response()


@bot_router.get("/autoreply/status")
async def bot_autoreply_status() -> dict[str, Any]:
    return _bot_activity_response()


@bot_router.get("/telegram-notifications")
async def bot_telegram_notifications() -> dict[str, Any]:
    return _telegram_notification_settings_response()


@bot_router.post("/telegram-notifications")
async def bot_set_telegram_notifications(request: TelegramNotificationSettingsRequest) -> dict[str, Any]:
    mode = _save_telegram_notification_mode(request.mode)
    _record_admin_log("info", "telegram_notification_mode_changed", {"mode": mode})
    return _telegram_notification_settings_response()


async def _process_unread(limit: int = 20) -> dict[str, Any]:
    settings = get_settings()
    services = process_unread.ProcessUnreadServices(
        settings=settings,
        avito=AvitoClient(settings),
        assistant=SalesAssistant(create_ai_client(settings)),
        get_runtime_store=get_runtime_store,
        to_http_error=_to_http_error,
        error_detail=_error_detail,
        record_admin_log=_record_admin_log,
        load_autoreply_pending=_load_autoreply_pending,
        save_autoreply_pending_item=_save_autoreply_pending_item,
        clear_autoreply_pending=_clear_autoreply_pending,
        load_processed_inbound_messages=_load_processed_inbound_messages,
        mark_processed_inbound_message=_mark_processed_inbound_message,
        load_manager_telegram_notified_message_keys=_load_manager_telegram_notified_message_keys,
        mark_manager_telegram_notified_message=_mark_manager_telegram_notified_message,
        load_telegram_notification_mode=_load_telegram_notification_mode,
        load_qualified_buying_chat_ids=_load_qualified_buying_chat_ids,
        add_qualified_buying_chat_id=_add_qualified_buying_chat_id,
        clear_automatic_takeover_for_qualified_chats=_clear_automatic_takeover_for_qualified_chats,
        manager_takeover_chat_ids=manager_takeover_chat_ids,
        persist_avito_chats=_persist_avito_chats,
        persist_avito_messages=_persist_avito_messages,
        track_bot_control_items=_track_bot_control_items,
        notify_manager_handoff=_notify_manager_handoff,
        notify_manager_folder_messages=_notify_manager_folder_messages,
        notify_inbound_messages=_notify_inbound_messages,
        latest_non_system_message=_latest_non_system_message,
        is_recent_chat=lambda chat: _is_recent_chat(chat, now=time.time()),
        message_processing_key=_message_processing_key,
        has_outbound_after_message=_has_outbound_after_message,
        estimate_reply_seconds=_estimate_reply_seconds,
        elapsed_ms=_elapsed_ms,
    )
    return await process_unread.process_unread(limit, services)


async def _bot_worker_loop() -> None:
    await autoreply_worker.worker_loop(_autoreply_worker_services())


def _bot_activity_response() -> dict[str, Any]:
    return autoreply_worker.activity_response(activity=bot_activity, task=bot_worker_task)


def _telegram_notification_settings_response() -> dict[str, Any]:
    mode = _load_telegram_notification_mode()
    return {
        "mode": mode,
        "notify_all": mode == "all",
        "notify_qualified_only": mode == "qualified",
    }


def _autoreply_worker_services() -> autoreply_worker.AutoreplyWorkerServices:
    return autoreply_worker.AutoreplyWorkerServices(
        process_unread=lambda limit: _process_unread(limit=limit),
        process_lock=process_unread_lock,
        activity=bot_activity,
        is_enabled=lambda: bot_worker_enabled,
        set_enabled=_set_bot_worker_enabled,
        save_enabled=_save_autoreply_enabled,
        record_admin_log=_record_admin_log,
        error_detail=_error_detail,
        interval_seconds=bot_worker_interval_seconds,
    )


def _chat_bot_control_response(chat_id: str) -> dict[str, Any]:
    _ensure_bot_control_state_loaded()
    manager_takeover = chat_id in manager_takeover_chat_ids
    return {
        "chat_id": chat_id,
        "manager_takeover": manager_takeover,
        "bot_enabled": not manager_takeover,
    }


@webhook_router.post("/webhooks/avito/messenger")
async def avito_webhook(payload: dict[str, Any]) -> dict[str, object]:
    webhook_events.insert(0, payload)
    del webhook_events[50:]
    chat_id = str(payload.get("chat_id") or payload.get("id") or "webhook")
    try:
        get_runtime_store().record_manager_action(chat_id, "webhook_received", payload)
    except Exception as exc:
        _record_admin_log("error", "webhook_persistence_failed", {"chat_id": chat_id, "error": _error_detail(exc)})
    _record_admin_log("info", "webhook_received", {"chat_id": chat_id, "type": payload.get("type")})
    return {"ok": True}


@webhook_router.get("/api/webhooks/avito/events")
async def avito_webhook_events() -> dict[str, Any]:
    return {"events": webhook_events}


app.include_router(web_router)
app.include_router(health_config_router)
app.include_router(storage_router)
app.include_router(ai_router)
app.include_router(avito_router)
app.include_router(bot_router)
app.include_router(webhook_router)


def get_runtime_store() -> RuntimeStore:
    global runtime_store, runtime_store_key
    runtime_store, runtime_store_key = runtime_services.get_runtime_store(
        settings=get_settings(),
        root=ROOT,
        runtime_dir=RUNTIME_DIR,
        current_store=runtime_store,
        current_key=runtime_store_key,
    )
    return runtime_store


async def _backup_worker_loop() -> None:
    await runtime_services.backup_worker_loop(
        get_settings=get_settings,
        get_store=get_runtime_store,
        activity=bot_activity,
        record_admin_log=_record_admin_log,
        error_detail=_error_detail,
    )


def _migrate_legacy_runtime_json_to_store() -> None:
    runtime_services.migrate_legacy_runtime_json_to_store(
        store=get_runtime_store(),
        autoreply_pending_path=AUTOREPLY_PENDING_PATH,
        autoreply_state_path=AUTOREPLY_STATE_PATH,
        bot_control_state_path=BOT_CONTROL_STATE_PATH,
    )


def _require_avito_live_sync(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.avito_live_sync_enabled:
        _record_admin_log("warning", "live_sync_blocked", {"reason": "AVITO_LIVE_SYNC_ENABLED=false"})
        raise HTTPException(status_code=409, detail="Avito live sync is disabled; using PostgreSQL cache only")


def _load_json_file(path: Path, *, default: Any) -> Any:
    return runtime_state.load_json_file(path, default=default)


def _persist_avito_chats(chats: list[dict[str, Any]]) -> None:
    avito_sync.persist_avito_chats(chats, _avito_sync_services())


def _persist_avito_messages(chat_id: str, messages_response: dict[str, Any]) -> None:
    avito_sync.persist_avito_messages(chat_id, messages_response, _avito_sync_services())


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


def _load_telegram_notification_mode() -> str:
    return runtime_state.load_telegram_notification_mode(get_runtime_store(), TELEGRAM_NOTIFICATION_MODE_STATE_KEY)


def _save_telegram_notification_mode(mode: str) -> str:
    return runtime_state.save_telegram_notification_mode(get_runtime_store(), TELEGRAM_NOTIFICATION_MODE_STATE_KEY, mode)


def _add_qualified_buying_chat_id(chat_id: str) -> None:
    chat_ids = _load_qualified_buying_chat_ids()
    chat_ids.add(chat_id)
    _save_qualified_buying_chat_ids(chat_ids)
    _clear_automatic_takeover_for_qualified_chats({chat_id})


async def _sync_qualified_buying_from_chats(client: AvitoClient, chats: list[dict[str, Any]]) -> list[str]:
    return await avito_sync.sync_qualified_buying_from_chats(client, chats, _avito_sync_services())


def _clear_automatic_takeover_for_qualified_chats(chat_ids: set[str]) -> None:
    _ensure_bot_control_state_loaded()
    normalized_chat_ids = _normalize_chat_ids(list(chat_ids))
    auto_takeover_chat_ids = (normalized_chat_ids & manager_takeover_chat_ids) - explicit_manager_takeover_chat_ids
    if not auto_takeover_chat_ids:
        return
    manager_takeover_chat_ids.difference_update(auto_takeover_chat_ids)
    _save_bot_control_state()


def _chat_summary_has_buying_intent(chat: dict[str, Any]) -> bool:
    return avito_sync.chat_summary_has_buying_intent(chat)


def _messages_have_buying_intent(messages_response: dict[str, Any]) -> bool:
    return avito_sync.messages_have_buying_intent(messages_response)


def _has_buying_intent(text: str) -> bool:
    return has_buying_intent(text)


def _normalize_chat_ids(chat_ids: list[Any]) -> set[str]:
    return runtime_state.normalize_chat_ids(chat_ids)


def _track_bot_control_items(chats: list[dict[str, Any]]) -> None:
    avito_sync.track_bot_control_items(chats, _avito_sync_services())


def _avito_sync_services() -> avito_sync.AvitoSyncServices:
    return avito_sync.AvitoSyncServices(
        get_runtime_store=get_runtime_store,
        record_admin_log=_record_admin_log,
        error_detail=_error_detail,
        load_qualified_buying_chat_ids=_load_qualified_buying_chat_ids,
        save_qualified_buying_chat_ids=_save_qualified_buying_chat_ids,
        clear_automatic_takeover_for_qualified_chats=_clear_automatic_takeover_for_qualified_chats,
        ensure_bot_control_state_loaded=_ensure_bot_control_state_loaded,
        save_bot_control_state=_save_bot_control_state,
        known_bot_control_chat_ids=known_bot_control_chat_ids,
        known_bot_control_item_keys=known_bot_control_item_keys,
        bot_control_state_path=BOT_CONTROL_STATE_PATH,
    )


def _to_http_error(exc: Exception) -> HTTPException:
    return http_errors.to_http_error(exc, record_log=_record_admin_log)


def create_ai_client(settings: Settings) -> DeepSeekClient | CodexAppServerClient | FallbackAIClient:
    return _create_ai_client(
        settings,
        deepseek_client_cls=DeepSeekClient,
        codex_client_cls=CodexAppServerClient,
    )


async def _notify_manager_handoff(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    handoff_reason: str | None,
    received_text: str | None,
) -> dict[str, object]:
    return await manager_notification_service.notify_manager_handoff(
        settings,
        chat=chat,
        chat_id=chat_id,
        handoff_reason=handoff_reason,
        received_text=received_text,
    )


async def _notify_manager_folder_messages(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    messages_response: dict[str, Any],
    notified_state: dict[str, set[str]],
) -> dict[str, object]:
    return await manager_notification_service.notify_manager_folder_messages(
        settings,
        chat=chat,
        chat_id=chat_id,
        messages_response=messages_response,
        notified_state=notified_state,
        message_processing_key=_message_processing_key,
        mark_notified_message=_mark_manager_telegram_notified_message,
        save_notified_state=_save_manager_telegram_notified_message_keys,
        record_admin_log=_record_admin_log,
        record_manager_action=get_runtime_store().record_manager_action,
    )


async def _notify_inbound_messages(
    settings: Settings,
    *,
    chat: dict[str, Any] | None = None,
    chat_id: str,
    messages_response: dict[str, Any],
    notified_state: dict[str, set[str]],
) -> dict[str, object]:
    return await manager_notification_service.notify_inbound_messages(
        settings,
        chat=chat,
        chat_id=chat_id,
        messages_response=messages_response,
        notified_state=notified_state,
        message_processing_key=_message_processing_key,
        mark_notified_message=_mark_manager_telegram_notified_message,
        record_admin_log=_record_admin_log,
        record_manager_action=get_runtime_store().record_manager_action,
    )


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
    return http_errors.error_detail(exc)


def _get_runtime_logger(settings: Settings | None = None):
    global runtime_logger, runtime_logger_key
    settings = settings or get_settings()
    key = (
        settings.ai_logger_level,
        settings.ai_logger_service,
        settings.ai_logger_project,
        settings.ai_logger_environment,
        settings.ai_logger_jsonl_path,
        settings.ai_logger_server_url,
        bool(settings.ai_logger_server_token),
    )
    if runtime_logger is not None and runtime_logger_key == key:
        return runtime_logger

    runtime_logger = create_runtime_logger(
        "avito-bot.runtime",
        admin_buffer=admin_logs,
        context={
            "project": settings.ai_logger_project or "avito-bot",
            "service": settings.ai_logger_service or "api",
            "environment": settings.ai_logger_environment or "local",
        },
    )
    runtime_logger_key = key
    return runtime_logger


def _record_admin_log(level: str, event: str, detail: Any | None = None) -> None:
    sanitized = safe_log_detail(detail)
    _get_runtime_logger().log(level, event, detail=sanitized)
