from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class DraftReplyRequest(BaseModel):
    chat: dict[str, Any] = Field(default_factory=dict)
    messages: dict[str, Any] = Field(default_factory=dict)


class ChatBotControlRequest(BaseModel):
    manager_takeover: bool


class QualifiedBuyingChatsRequest(BaseModel):
    chat_ids: list[str] = Field(default_factory=list)


class TelegramNotificationSettingsRequest(BaseModel):
    mode: str = Field(pattern="^(all|qualified)$")


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
