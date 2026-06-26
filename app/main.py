from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.assistant import SalesAssistant, order_messages
from app.avito_client import AvitoClient, AvitoConfigError
from app.config import get_settings
from app.deepseek_client import DeepSeekClient, DeepSeekConfigError


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "app" / "static"
RUNTIME_DIR = ROOT / ".codex-runtime"
AUTOREPLY_PENDING_PATH = RUNTIME_DIR / "autoreply-pending.json"
AUTOREPLY_STATE_PATH = RUNTIME_DIR / "autoreply-state.json"
BOT_CONTROL_STATE_PATH = RUNTIME_DIR / "bot-control-state.json"

webhook_events: list[dict[str, Any]] = []
manager_takeover_chat_ids: set[str] = set()
known_bot_control_chat_ids: set[str] = set()
known_bot_control_item_keys: set[str] = set()
bot_control_state_loaded = False
process_unread_lock = asyncio.Lock()
bot_worker_task: asyncio.Task[None] | None = None
bot_worker_enabled = False
bot_worker_interval_seconds = 5
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
    await _restore_bot_worker_state()
    yield


app = FastAPI(title="avito-bot", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class DraftReplyRequest(BaseModel):
    chat: dict[str, Any] = Field(default_factory=dict)
    messages: dict[str, Any] = Field(default_factory=dict)


class ChatBotControlRequest(BaseModel):
    manager_takeover: bool


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


@app.post("/api/ai/ping")
async def ai_ping() -> dict[str, object]:
    client = DeepSeekClient(get_settings())
    try:
        reply = await client.ping()
    except Exception as exc:
        raise _to_http_error(exc) from exc
    return {"ok": reply.lower() == "ok", "reply": reply}


@app.post("/api/ai/draft-reply")
async def ai_draft_reply(request: DraftReplyRequest) -> dict[str, Any]:
    assistant = SalesAssistant(DeepSeekClient(get_settings()))
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
    _apply_manual_default_for_new_items(list(response.get("chats", [])))
    return response


@app.get("/api/avito/chats/{chat_id}")
async def avito_chat(chat_id: str) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        return await client.get_chat(chat_id)
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.get("/api/avito/chats/{chat_id}/messages")
async def avito_messages(chat_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        return await client.get_messages(chat_id, limit=limit, offset=offset)
    except Exception as exc:
        raise _to_http_error(exc) from exc


@app.post("/api/avito/chats/{chat_id}/messages")
async def avito_send_message(chat_id: str, request: SendMessageRequest) -> dict[str, Any]:
    client = AvitoClient(get_settings())
    try:
        return await client.send_text_message(chat_id, request.text)
    except Exception as exc:
        raise _to_http_error(exc) from exc


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
    return _chat_bot_control_response(chat_id)


@app.post("/api/avito/chats/{chat_id}/ai-draft")
async def avito_ai_draft(chat_id: str) -> dict[str, Any]:
    settings = get_settings()
    avito = AvitoClient(settings)
    assistant = SalesAssistant(DeepSeekClient(settings))
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
    assistant = SalesAssistant(DeepSeekClient(settings))
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
    return {"ok": True}


@app.get("/api/webhooks/avito/events")
async def avito_webhook_events() -> dict[str, Any]:
    return {"events": webhook_events}


def _load_autoreply_pending() -> dict[str, dict[str, Any]]:
    if not AUTOREPLY_PENDING_PATH.exists():
        return {}
    try:
        data = json.loads(AUTOREPLY_PENDING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    pending: dict[str, dict[str, Any]] = {}
    for chat_id, item in data.items():
        if isinstance(chat_id, str) and isinstance(item, dict):
            pending[chat_id] = item
    return pending


def _write_autoreply_pending(pending: dict[str, dict[str, Any]]) -> None:
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
        AUTOREPLY_PENDING_PATH.unlink(missing_ok=True)


def _load_autoreply_enabled() -> bool:
    if not AUTOREPLY_STATE_PATH.exists():
        return False
    try:
        data = json.loads(AUTOREPLY_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(isinstance(data, dict) and data.get("enabled") is True)


def _save_autoreply_enabled(enabled: bool) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = AUTOREPLY_STATE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps({"enabled": enabled}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(AUTOREPLY_STATE_PATH)


def _ensure_bot_control_state_loaded() -> None:
    global bot_control_state_loaded
    if bot_control_state_loaded:
        return
    bot_control_state_loaded = True
    if not BOT_CONTROL_STATE_PATH.exists():
        return
    try:
        data = json.loads(BOT_CONTROL_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = BOT_CONTROL_STATE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(
            {
                "known_chat_ids": sorted(known_bot_control_chat_ids),
                "known_item_keys": sorted(known_bot_control_item_keys),
                "manager_takeover_chat_ids": sorted(manager_takeover_chat_ids),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_path.replace(BOT_CONTROL_STATE_PATH)


def _apply_manual_default_for_new_items(chats: list[dict[str, Any]]) -> None:
    _ensure_bot_control_state_loaded()
    chat_ids_by_item_key: dict[str, list[str]] = {}
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        item_key = _chat_item_key(chat)
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


def _chat_item_key(chat: dict[str, Any]) -> str:
    item = _chat_item_context(chat)
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


def _chat_item_context(chat: dict[str, Any]) -> dict[str, Any]:
    context = chat.get("context")
    if isinstance(context, dict) and isinstance(context.get("value"), dict):
        return context["value"]
    item = chat.get("item")
    if isinstance(item, dict):
        return item
    return {}


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AvitoConfigError, DeepSeekConfigError)):
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
