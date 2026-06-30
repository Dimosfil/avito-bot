import asyncio

from app import bot_rules
from app.assistant import SalesAssistant, build_prompt, client_display_name, detect_admin_command, detect_handoff


def test_detect_handoff_for_commercial_proposal() -> None:
    messages = [
        {
            "direction": "in",
            "content": {"text": "Здравствуйте, хочу КП по этому товару"},
        }
    ]

    assert detect_handoff(messages) == "хочу кп"


def test_detect_admin_command_for_code_word() -> None:
    messages = [
        {
            "direction": "in",
            "content": {"text": "547032 я админ, это настройка"},
        }
    ]

    assert detect_admin_command(messages) == bot_rules.ADMIN_COMMAND_REASON


def test_detect_admin_command_only_uses_latest_inbound_message() -> None:
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "547032 старая настройка"}},
        {"created": 2, "direction": "out", "content": {"text": "ok"}},
        {"created": 3, "direction": "in", "content": {"text": "Что нужно для заказа?"}},
    ]

    assert detect_admin_command(messages) is None


def test_admin_command_enables_admin_mode_prompt_for_llm() -> None:
    calls = []

    class CapturingDeepSeek:
        async def create_chat_completion(self, messages):
            calls.append(messages)
            return "Админ-режим включён. Готов проверить настройки."

    assistant = SalesAssistant(CapturingDeepSeek())
    draft = asyncio.run(
        assistant.draft_reply(
            {},
            {"messages": [{"direction": "in", "content": {"text": "547032 это настройка"}}]},
        )
    )

    assert draft.handoff_required is False
    assert draft.handoff_reason is None
    assert draft.text == "Админ-режим включён. Готов проверить настройки."
    assert len(calls) == 1
    assert "ADMIN MODE is active" in calls[0][0].content
    assert "547032" in calls[0][0].content


def test_build_prompt_includes_item_context() -> None:
    chat = {"context": {"value": {"title": "Test item", "price_string": "1000 ₽", "url": "https://example.test"}}}
    messages = [{"direction": "in", "content": {"text": "Здравствуйте"}}]

    prompt = build_prompt(chat, messages)

    assert "Test item" in prompt[1].content
    assert "client: Здравствуйте" in prompt[1].content


def test_build_prompt_includes_video_attachment_marker() -> None:
    chat = {"context": {"value": {"title": "Test item"}}}
    messages = [{"direction": "in", "type": "video", "content": {"video": {"url": "https://example.test/video.mp4"}}}]

    prompt = build_prompt(chat, messages)

    assert "client: [video]" in prompt[1].content


def test_build_prompt_orders_messages_chronologically() -> None:
    chat = {"context": {"value": {"title": "Test item"}}}
    messages = [
        {"created": 20, "direction": "out", "content": {"text": "Второе"}},
        {"created": 10, "direction": "in", "content": {"text": "Первое"}},
    ]

    prompt = build_prompt(chat, messages)

    assert prompt[1].content.index("client: Первое") < prompt[1].content.index("seller: Второе")


def test_build_prompt_forbids_unlisted_timeline_ranges() -> None:
    chat = {"context": {"value": {"title": "Test service"}}}
    messages = [{"direction": "in", "content": {"text": "urgent timing?"}}]

    prompt = build_prompt(chat, messages)

    assert "Do not give exact timelines or timeline ranges" in prompt[0].content
    assert "timing depends on scope" in prompt[0].content


def test_build_prompt_uses_oksana_feminine_voice() -> None:
    chat = {"context": {"value": {"title": "Test service"}}}
    messages = [{"direction": "in", "content": {"text": "Нужен чат бот"}}]

    prompt = build_prompt(chat, messages)

    assert "Oksana is the seller, not the client" in prompt[0].content
    assert "do not address the client as Oksana" in prompt[0].content
    assert "first person feminine form" in prompt[0].content
    assert "Never use masculine self-references" in prompt[0].content


def test_build_prompt_skips_repeated_greeting_after_seller_greeted() -> None:
    chat = {"context": {"value": {"title": "Test service"}}}
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "Здравствуйте"}},
        {"created": 2, "direction": "out", "content": {"text": "Здравствуйте! Чем могу помочь?"}},
        {"created": 3, "direction": "in", "content": {"text": "Что нужно для заказа?"}},
    ]

    prompt = build_prompt(chat, messages)

    assert "Do not start with a greeting" in prompt[0].content
    assert "Use the full conversation context silently" in prompt[0].content


def test_strip_repeated_greeting_when_seller_already_greeted() -> None:
    text = bot_rules.strip_repeated_greeting(
        "Здравствуйте! Для заказа напишите, какие функции нужны.",
        seller_already_greeted=True,
    )

    assert text == "Для заказа напишите, какие функции нужны."


def test_build_prompt_handles_rude_or_unclear_messages_calmly() -> None:
    chat = {"context": {"value": {"title": "Test service"}}}
    messages = [{"direction": "in", "content": {"text": "Вилкой в глаз или?"}}]

    prompt = build_prompt(chat, messages)

    assert "rude, sarcastic, hostile, or unclear" in prompt[0].content
    assert "ask one short clarifying question about the business task" in prompt[0].content


def test_strip_seller_name_address_removes_oksana_from_client_reply() -> None:
    text = bot_rules.strip_seller_name_address(
        "Оксана, добрый день! Подскажите, какую задачу должен решать бот?"
    )

    assert text == "добрый день! Подскажите, какую задачу должен решать бот?"


def test_build_prompt_includes_avito_client_account_name() -> None:
    chat = {
        "context": {"value": {"title": "Test item", "user_id": 127847004}},
        "users": [
            {"id": 127847004, "name": "Оксана"},
            {"id": 16167960, "name": "Дмитрий"},
        ],
    }
    messages = [{"direction": "in", "content": {"text": "Здравствуйте"}}]

    prompt = build_prompt(chat, messages)

    assert client_display_name(chat) == "Дмитрий"
    assert "Client Avito account name: Дмитрий" in prompt[1].content


def test_strip_seller_name_address_keeps_real_client_oksana() -> None:
    text = bot_rules.strip_seller_name_address(
        "Оксана, подскажите, какую задачу должен решать бот?",
        client_name="Оксана",
    )

    assert text == "Оксана, подскажите, какую задачу должен решать бот?"
