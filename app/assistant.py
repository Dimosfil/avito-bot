from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import bot_rules
from app.deepseek_client import ChatMessage, DeepSeekClient


@dataclass(frozen=True)
class AssistantDraft:
    text: str
    handoff_required: bool
    handoff_reason: str | None


class SalesAssistant:
    def __init__(self, deepseek: DeepSeekClient) -> None:
        self._deepseek = deepseek

    async def draft_reply(self, chat: dict[str, Any], messages_response: dict[str, Any]) -> AssistantDraft:
        messages = order_messages(list(messages_response.get("messages", [])))
        handoff_reason = detect_handoff(messages)
        if handoff_reason:
            return AssistantDraft(
                text=(
                    "Клиент показывает готовность к сделке. "
                    "Лучше подключить менеджера и не отправлять автоответ."
                ),
                handoff_required=True,
                handoff_reason=handoff_reason,
            )

        prompt_messages = build_prompt(chat, messages)
        text = await self._deepseek.create_chat_completion(prompt_messages)
        text = bot_rules.strip_repeated_greeting(text, seller_already_greeted=seller_already_greeted(messages))
        return AssistantDraft(text=text, handoff_required=False, handoff_reason=None)


def detect_handoff(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(order_messages(messages)):
        if message.get("direction") != "in" or message.get("type") == "system":
            continue
        text = _message_text(message).lower()
        for phrase in bot_rules.HANDOFF_PHRASES:
            if phrase in text:
                return phrase
    return None


def build_prompt(chat: dict[str, Any], messages: list[dict[str, Any]]) -> list[ChatMessage]:
    item = (chat.get("context") or {}).get("value") or {}
    title = item.get("title") or "unknown item"
    price = item.get("price_string") or "unknown price"
    url = item.get("url") or ""

    transcript = []
    for message in order_messages(messages)[-12:]:
        if message.get("type") == "system":
            continue
        role = "client" if message.get("direction") == "in" else "seller"
        text = _message_text(message)
        if text:
            transcript.append(f"{role}: {text}")

    return [
        ChatMessage(
            role="system",
            content=bot_rules.build_system_prompt(seller_already_greeted=seller_already_greeted(messages)),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Avito item: {title}\n"
                f"Price: {price}\n"
                f"URL: {url}\n\n"
                "Conversation:\n"
                + "\n".join(transcript)
                + "\n\nDraft the next seller reply."
            ),
        ),
    ]


def order_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(messages, key=lambda message: int(message.get("created") or message.get("created_at") or 0))


def seller_already_greeted(messages: list[dict[str, Any]]) -> bool:
    for message in order_messages(messages):
        if message.get("direction") == "out" and bot_rules.starts_with_greeting(_message_text(message)):
            return True
    return False


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content") or {}
    if isinstance(content.get("text"), str):
        return content["text"]
    if isinstance(content.get("link"), dict) and isinstance(content["link"].get("text"), str):
        return content["link"]["text"]
    if "image" in content:
        return "[image]"
    if "voice" in content:
        return "[voice]"
    return ""
