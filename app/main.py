from __future__ import annotations

import asyncio
import json
import time
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
from app.assistant import SalesAssistant, order_messages
from app.avito_payload import chat_item_key
from app.avito_client import AvitoClient, AvitoConfigError
from app.codex_app_server_client import CodexAppServerClient, CodexAppServerConfigError
from app.config import get_settings
from app.config import Settings
from app.deepseek_client import DeepSeekClient, DeepSeekConfigError
from app.storage import RuntimeStore


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "app" / "static"
RUNTIME_DIR = ROOT / ".codex-runtime"
AUTOREPLY_PENDING_PATH = RUNTIME_DIR / "autoreply-pending.json"
AUTOREPLY_STATE_PATH = RUNTIME_DIR / "autoreply-state.json"
BOT_CONTROL_STATE_PATH = RUNTIME_DIR / "bot-control-state.json"
QUALIFIED_BUYING_STATE_KEY = "qualified_buying_chat_ids"

webhook_events: list[dict[str, Any]] = []
manager_takeover_chat_ids: set[str] = set()
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
    client = AvitoClient(get_settings())
    try:
        return await client.get_account_self()
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.get("/api/avito/chats")
async def avito_chats(limit: int = 20, offset: int = 0, unread_only: bool = False) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        response = await client.get_chats(limit=limit, offset=offset, unread_only=unread_only)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    _persist_avito_chats(list(response.get("chats", [])))
    _apply_manual_default_for_new_items(list(response.get("chats", [])))
    return response


@app.get("/api/avito/chats/{chat_id}")
async def avito_chat(chat_id: str) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        response = await client.get_chat(chat_id)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    _persist_avito_chats([{**response, "id": response.get("id") or chat_id}])
    return response


@app.get("/api/avito/chats/{chat_id}/messages")
async def avito_messages(chat_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        response = await client.get_messages(chat_id, limit=limit, offset=offset)
    except Exception as exc:
        raise _to_http_error(exc) from exc
    _persist_avito_messages(chat_id, response)
    return response


@app.post("/api/avito/chats/{chat_id}/messages")
async def avito_send_message(chat_id: str, request: SendMessageRequest) -> dict[str, Any]:
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
    else:
        manager_takeover_chat_ids.discard(chat_id)
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
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@app.post("/api/avito/qualified-buying-chats")
async def avito_save_qualified_buying_chats(request: QualifiedBuyingChatsRequest) -> dict[str, Any]:
    chat_ids = _load_qualified_buying_chat_ids()
    chat_ids.update(_normalize_chat_ids(request.chat_ids))
    _save_qualified_buying_chat_ids(chat_ids)
    return {"chat_ids": sorted(chat_ids), "count": len(chat_ids)}


@app.post("/api/avito/chats/{chat_id}/ai-draft")
async def avito_ai_draft(chat_id: str) -> dict[str, Any]:
    settings = get_settings()
    avito = AvitoClient(settings)
    assistant = SalesAssistant(create_ai_client(settings))
    try:
        chat = await avito.get_chat(chat_id)
        messages = await avito.get_messages(chat_id, limit=30)
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
    async with process_unread_lock:
        return await _process_unread(limit=limit)


@app.post("/api/bot/autoreply/start")
async def bot_autoreply_start() -> dict[str, Any]:
    global bot_worker_enabled, bot_worker_task
    settings = get_settings()
    if not settings.has_avito_credentials:
        raise HTTPException(status_code=400, detail="AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required")
    bot_worker_enabled = True
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

    try:
        chats_response = await avito.get_chats(limit=limit, unread_only=True)
    except Exception as exc:
        raise _to_http_error(exc) from exc

    chats = list(chats_response.get("chats", []))
    seen_chat_ids = {str(chat.get("id") or "") for chat in chats}
    for chat_id in list(pending):
        if chat_id and chat_id not in seen_chat_ids:
            try:
                chat = await avito.get_chat(chat_id)
                chat.setdefault("id", chat_id)
                chats.append(chat)
            except Exception:
                chats.append({"id": chat_id})

    _persist_avito_chats(chats)
    _apply_manual_default_for_new_items(chats)

    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            results.append(ProcessedUnreadChat(chat_id="", status="skipped", error="missing chat id"))
            continue
        if chat_id in manager_takeover_chat_ids:
            results.append(ProcessedUnreadChat(chat_id=chat_id, status="manager_active"))
            continue

        try:
            messages = await avito.get_messages(chat_id, limit=30)
            _persist_avito_messages(chat_id, messages)
            latest_message = _latest_non_system_message(messages)
            pending_item = pending.get(chat_id)
            if not latest_message or latest_message.get("direction") != "in":
                status = "answered" if _has_outbound_after_message(messages, pending_item) else "skipped"
                _clear_autoreply_pending(chat_id)
                results.append(ProcessedUnreadChat(chat_id=chat_id, status=status))
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
                        duration_ms=_elapsed_ms(accepted_at),
                    )
                )
                continue

            sent = await avito.send_text_message(chat_id, draft.text.strip())
            get_runtime_store().record_manager_action(
                chat_id,
                "ai_auto_reply_sent",
                {"text": draft.text.strip(), "avito_response": sent},
            )
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


def _load_json_file(path: Path, *, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


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
    data = get_runtime_store().get_state("autoreply_pending")
    if data is None:
        data = _load_json_file(AUTOREPLY_PENDING_PATH, default={}) if AUTOREPLY_PENDING_PATH.exists() else {}
        if isinstance(data, dict):
            get_runtime_store().set_state("autoreply_pending", data)
    if not isinstance(data, dict):
        return {}
    pending: dict[str, dict[str, Any]] = {}
    for chat_id, item in data.items():
        if isinstance(chat_id, str) and isinstance(item, dict):
            pending[chat_id] = item
    return pending


def _write_autoreply_pending(pending: dict[str, dict[str, Any]]) -> None:
    get_runtime_store().set_state("autoreply_pending", pending)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = AUTOREPLY_PENDING_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(AUTOREPLY_PENDING_PATH)


def _save_autoreply_pending_item(chat_id: str, item: dict[str, Any]) -> None:
    pending = _load_autoreply_pending()
    pending[chat_id] = item
    _write_autoreply_pending(pending)


def _clear_autoreply_pending(chat_id: str) -> None:
    pending = _load_autoreply_pending()
    if chat_id not in pending:
        return
    del pending[chat_id]
    if pending:
        _write_autoreply_pending(pending)
    else:
        get_runtime_store().set_state("autoreply_pending", {})
        AUTOREPLY_PENDING_PATH.unlink(missing_ok=True)


def _load_autoreply_enabled() -> bool:
    data = get_runtime_store().get_state("autoreply_enabled")
    if data is None:
        legacy = _load_json_file(AUTOREPLY_STATE_PATH, default={}) if AUTOREPLY_STATE_PATH.exists() else {}
        data = bool(isinstance(legacy, dict) and legacy.get("enabled") is True)
        get_runtime_store().set_state("autoreply_enabled", data)
    return bool(data)


def _save_autoreply_enabled(enabled: bool) -> None:
    get_runtime_store().set_state("autoreply_enabled", enabled)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = AUTOREPLY_STATE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps({"enabled": enabled}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(AUTOREPLY_STATE_PATH)


def _ensure_bot_control_state_loaded() -> None:
    global bot_control_state_loaded
    if bot_control_state_loaded:
        return
    bot_control_state_loaded = True
    data = get_runtime_store().get_state("bot_control")
    if data is None and BOT_CONTROL_STATE_PATH.exists():
        data = _load_json_file(BOT_CONTROL_STATE_PATH, default={})
        if isinstance(data, dict):
            get_runtime_store().set_state("bot_control", data)
    if data is None:
        return
    if not isinstance(data, dict):
        return

    known_chat_ids = data.get("known_chat_ids", [])
    known_item_keys = data.get("known_item_keys", [])
    takeover_chat_ids = data.get("manager_takeover_chat_ids", [])
    if isinstance(known_chat_ids, list):
        known_bot_control_chat_ids.update(str(chat_id) for chat_id in known_chat_ids if chat_id)
    if isinstance(known_item_keys, list):
        known_bot_control_item_keys.update(str(item_key) for item_key in known_item_keys if item_key)
    if isinstance(takeover_chat_ids, list):
        manager_takeover_chat_ids.update(str(chat_id) for chat_id in takeover_chat_ids if chat_id)


def _save_bot_control_state() -> None:
    data = {
        "known_chat_ids": sorted(known_bot_control_chat_ids),
        "known_item_keys": sorted(known_bot_control_item_keys),
        "manager_takeover_chat_ids": sorted(manager_takeover_chat_ids),
    }
    get_runtime_store().set_state("bot_control", data)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = BOT_CONTROL_STATE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(BOT_CONTROL_STATE_PATH)


def _load_qualified_buying_chat_ids() -> set[str]:
    data = get_runtime_store().get_state(QUALIFIED_BUYING_STATE_KEY)
    if isinstance(data, list):
        return _normalize_chat_ids(data)
    if isinstance(data, dict):
        return _normalize_chat_ids(data.get("chat_ids", []))
    return set()


def _save_qualified_buying_chat_ids(chat_ids: set[str]) -> None:
    get_runtime_store().set_state(QUALIFIED_BUYING_STATE_KEY, sorted(chat_ids))


def _normalize_chat_ids(chat_ids: list[Any]) -> set[str]:
    return {str(chat_id).strip() for chat_id in chat_ids if str(chat_id).strip()}


def _apply_manual_default_for_new_items(chats: list[dict[str, Any]]) -> None:
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
                known_bot_control_chat_ids.add(chat_id)
            if not is_new_item:
                continue
            manager_takeover_chat_ids.update(chat_ids)
            changed = True

    if changed:
        _save_bot_control_state()


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AvitoConfigError, DeepSeekConfigError, CodexAppServerConfigError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        detail: object
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        return HTTPException(status_code=exc.response.status_code, detail=detail)
    if isinstance(exc, httpx.RequestError):
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


def _latest_non_system_message(messages_response: dict[str, Any]) -> dict[str, Any] | None:
    messages = order_messages(list(messages_response.get("messages", [])))
    for message in reversed(messages):
        if message.get("type") != "system":
            return message
    return None


def _has_outbound_after_message(messages_response: dict[str, Any], pending_item: dict[str, Any] | None) -> bool:
    if not pending_item:
        return False
    pending_message_id = str(pending_item.get("message_id") or "")
    messages = [message for message in order_messages(list(messages_response.get("messages", []))) if message.get("type") != "system"]
    if not pending_message_id:
        return bool(messages and messages[-1].get("direction") == "out")

    found_pending = False
    for message in messages:
        if found_pending and message.get("direction") == "out":
            return True
        if str(message.get("id") or "") == pending_message_id:
            found_pending = True
    return False


def _estimate_reply_seconds(message: dict[str, Any]) -> int:
    text = ((message.get("content") or {}).get("text") or "").strip()
    return max(8, min(30, 10 + len(text) // 80 * 3))


def _elapsed_ms(started_at: float, finished_at: float | None = None) -> int:
    return round(((finished_at or time.time()) - started_at) * 1000)


def _error_detail(exc: Exception) -> object:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json()
        except ValueError:
            return exc.response.text
    return str(exc) or exc.__class__.__name__
