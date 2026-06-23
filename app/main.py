from __future__ import annotations

import asyncio
import time
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

app = FastAPI(title="avito-bot", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

webhook_events: list[dict[str, Any]] = []
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


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class DraftReplyRequest(BaseModel):
    chat: dict[str, Any] = Field(default_factory=dict)
    messages: dict[str, Any] = Field(default_factory=dict)


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
        return await client.get_chats(limit=limit, offset=offset, unread_only=unread_only)
    except Exception as exc:
        raise _to_http_error(exc) from exc


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
    return _bot_activity_response()


@app.post("/api/bot/autoreply/stop")
async def bot_autoreply_stop() -> dict[str, Any]:
    global bot_worker_enabled
    bot_worker_enabled = False
    bot_activity["enabled"] = False
    return _bot_activity_response()


@app.get("/api/bot/autoreply/status")
async def bot_autoreply_status() -> dict[str, Any]:
    return _bot_activity_response()


async def _process_unread(limit: int = 20) -> dict[str, Any]:
    settings = get_settings()
    avito = AvitoClient(settings)
    assistant = SalesAssistant(DeepSeekClient(settings))
    results: list[ProcessedUnreadChat] = []

    try:
        chats_response = await avito.get_chats(limit=limit, unread_only=True)
    except Exception as exc:
        raise _to_http_error(exc) from exc

    for chat in chats_response.get("chats", []):
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            results.append(ProcessedUnreadChat(chat_id="", status="skipped", error="missing chat id"))
            continue

        try:
            messages = await avito.get_messages(chat_id, limit=30)
            latest_message = _latest_non_system_message(messages)
            if not latest_message or latest_message.get("direction") != "in":
                results.append(ProcessedUnreadChat(chat_id=chat_id, status="skipped"))
                continue

            accepted_at = time.time()
            estimate_seconds = _estimate_reply_seconds(latest_message)
            draft = await assistant.draft_reply(chat, messages)
            if draft.handoff_required:
                results.append(
                    ProcessedUnreadChat(
                        chat_id=chat_id,
                        status="handoff_required",
                        handoff_required=True,
                        handoff_reason=draft.handoff_reason,
                        received_message_id=str(latest_message.get("id") or ""),
                        accepted_at=accepted_at,
                        estimate_seconds=estimate_seconds,
                        estimated_reply_at=accepted_at + estimate_seconds,
                        duration_ms=_elapsed_ms(accepted_at),
                    )
                )
                continue

            sent = await avito.send_text_message(chat_id, draft.text.strip())
            sent_at = time.time()
            await avito.mark_chat_read(chat_id)
            results.append(
                ProcessedUnreadChat(
                    chat_id=chat_id,
                    status="sent",
                    received_message_id=str(latest_message.get("id") or ""),
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


@app.post("/webhooks/avito/messenger")
async def avito_webhook(payload: dict[str, Any]) -> dict[str, object]:
    webhook_events.insert(0, payload)
    del webhook_events[50:]
    return {"ok": True}


@app.get("/api/webhooks/avito/events")
async def avito_webhook_events() -> dict[str, Any]:
    return {"events": webhook_events}


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
