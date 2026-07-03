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
        admin_mode = detect_admin_command(messages) is not None
        handoff_reason = None if admin_mode else detect_handoff(messages)
        if handoff_reason:
            return AssistantDraft(
                text=(
                    "Приняла, передам информацию менеджеру. "
                    "С вами свяжутся для уточнения деталей."
                ),
                handoff_required=True,
                handoff_reason=handoff_reason,
            )

        prompt_messages = build_prompt(chat, messages, admin_mode=admin_mode)
        text = await self._deepseek.create_chat_completion(prompt_messages)
        text = bot_rules.redact_admin_code(text)
        text = bot_rules.strip_seller_name_address(text, client_name=client_display_name(chat))
        text = bot_rules.strip_repeated_greeting(text, seller_already_greeted=seller_already_greeted(messages))
        text = bot_rules.sanitize_outgoing_text(text)
        text = bot_rules.enforce_seller_feminine_voice(text)
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
    return None


def detect_admin_command(messages: list[dict[str, Any]]) -> str | None:
    admin_mode = False
    for message in order_messages(messages):
        if message.get("direction") != "in" or message.get("type") == "system":
            continue
        text = _message_text(message)
        if bot_rules.ADMIN_CODE in text:
            admin_mode = True
        if bot_rules.ADMIN_MODE_DISABLE_RE.search(text):
            admin_mode = False
    return bot_rules.ADMIN_COMMAND_REASON if admin_mode else None


def build_prompt(chat: dict[str, Any], messages: list[dict[str, Any]], *, admin_mode: bool | None = None) -> list[ChatMessage]:
    if admin_mode is None:
        admin_mode = detect_admin_command(messages) is not None
    item = (chat.get("context") or {}).get("value") or {}
    title = item.get("title") or "unknown item"
    price = item.get("price_string") or "unknown price"
    url = item.get("url") or ""
    client_name = client_display_name(chat) or "unknown"

    transcript = []
    client_texts: list[str] = []
    seller_texts: list[str] = []
    for message in order_messages(messages)[-12:]:
        if message.get("type") == "system":
            continue
        role = "client" if message.get("direction") == "in" else "seller"
        text = bot_rules.redact_admin_code(_message_text(message))
        if text:
            transcript.append(f"{role}: {text}")
            if role == "client":
                client_texts.append(text)
            else:
                seller_texts.append(text)

    dialogue_guidance = bot_rules.build_dialogue_guidance(
        client_texts=client_texts,
        seller_texts=seller_texts,
        item_price=price,
        admin_mode=admin_mode,
    )

    return [
        ChatMessage(
            role="system",
            content=bot_rules.build_system_prompt(
                seller_already_greeted=seller_already_greeted(messages),
                admin_mode=admin_mode,
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Avito item: {title}\n"
                f"Price: {price}\n"
                f"URL: {url}\n\n"
                f"Client Avito account name: {client_name}\n\n"
                f"Dialogue guidance: {dialogue_guidance}\n\n"
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


def client_display_name(chat: dict[str, Any]) -> str:
    item = (chat.get("context") or {}).get("value") or {}
    seller_id = _string_id(item.get("user_id") or chat.get("seller_id") or chat.get("owner_id") or chat.get("account_id"))

    for user in _chat_users(chat):
        user_id = _string_id(user.get("id") or user.get("user_id") or user.get("author_id"))
        if seller_id and user_id == seller_id:
            continue
        name = _clean_name(user.get("name") or user.get("display_name") or user.get("title"))
        if name:
            return name

    return ""


def _chat_users(chat: dict[str, Any]) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    for source in (chat.get("users"), chat.get("participants"), chat.get("members"), (chat.get("context") or {}).get("users")):
        if isinstance(source, list):
            users.extend(user for user in source if isinstance(user, dict))
    return users


def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _string_id(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content") or {}
    if isinstance(content.get("text"), str):
        return content["text"]
    if isinstance(content.get("link"), dict) and isinstance(content["link"].get("text"), str):
        return content["link"]["text"]
    if "image" in content:
        return "[image]"
    if "video" in content:
        return "[video]"
    if "voice" in content:
        return "[voice]"
    return ""
