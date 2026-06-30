import asyncio
import json

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


def test_detect_admin_command_stays_active_until_disable_command() -> None:
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "547032 старая настройка"}},
        {"created": 2, "direction": "out", "content": {"text": "ok"}},
        {"created": 3, "direction": "in", "content": {"text": "Что нужно для заказа?"}},
    ]

    assert detect_admin_command(messages) == bot_rules.ADMIN_COMMAND_REASON


def test_detect_admin_command_disables_admin_mode_by_phrase() -> None:
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "547032 включаю отладку"}},
        {"created": 2, "direction": "out", "content": {"text": "Админ-режим включён."}},
        {"created": 3, "direction": "in", "content": {"text": "Выключить отладку"}},
    ]

    assert detect_admin_command(messages) is None


def test_admin_mode_suppresses_handoff_after_code_until_disabled() -> None:
    calls = []

    class CapturingDeepSeek:
        async def create_chat_completion(self, messages):
            calls.append(messages)
            return "Админ-режим активен, КП не передаю менеджеру."

    assistant = SalesAssistant(CapturingDeepSeek())
    draft = asyncio.run(
        assistant.draft_reply(
            {},
            {
                "messages": [
                    {"created": 1, "direction": "in", "content": {"text": "547032 включаю отладку"}},
                    {"created": 2, "direction": "out", "content": {"text": "Админ-режим включён."}},
                    {"created": 3, "direction": "in", "content": {"text": "хочу КП, проверь правило"}},
                ]
            },
        )
    )

    assert draft.handoff_required is False
    assert draft.handoff_reason is None
    assert "ADMIN MODE is active" in calls[0][0].content


def test_admin_mode_followup_prompt_does_not_include_sales_handoff_guidance() -> None:
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "547032"}},
        {"created": 2, "direction": "out", "content": {"text": "Админ-режим включён."}},
        {"created": 3, "direction": "in", "content": {"text": "перечисли основные правила"}},
    ]

    prompt = build_prompt({}, messages)

    assert detect_admin_command(messages) == bot_rules.ADMIN_COMMAND_REASON
    assert "ADMIN MODE is active" in prompt[0].content
    assert "Admin dialogue playbook" in prompt[1].content
    assert "Manager handoff is for clear buying intent" not in prompt[1].content
    assert "Mention manager handoff only once" not in prompt[0].content


def test_bot_rules_can_load_handoff_phrase_from_json_without_python_change(tmp_path) -> None:
    data = json.loads(bot_rules.DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
    data["handoff_phrases"].append("готов обсудить договор")
    rules_path = tmp_path / "bot-rules.json"
    rules_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    loaded_rules = bot_rules.load_bot_rules(rules_path)

    assert "готов обсудить договор" in loaded_rules.handoff_phrases


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


def test_draft_reply_sanitizes_markdown_and_stray_symbols() -> None:
    class CapturingDeepSeek:
        async def create_chat_completion(self, messages):
            return "**Mode**: active\n- **Rules**: use `plain text`. Which\u2030scenario?"

    assistant = SalesAssistant(CapturingDeepSeek())
    draft = asyncio.run(
        assistant.draft_reply(
            {},
            {"messages": [{"direction": "in", "content": {"text": "547032 rules"}}]},
        )
    )

    assert draft.text == "Mode: active\n- Rules: use plain text. Which scenario?"
    assert "**" not in draft.text
    assert "`" not in draft.text
    assert "\u2030" not in draft.text


def test_admin_prompt_forbids_markdown_formatting() -> None:
    prompt = build_prompt({}, [{"direction": "in", "content": {"text": "547032 rules"}}])

    assert "Use plain text only" in prompt[0].content
    assert "Do not use Markdown formatting" in prompt[0].content


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
    assert "answer directly with the known starting price" in prompt[0].content


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


def test_build_prompt_guides_price_questions_to_entry_price() -> None:
    chat = {"context": {"value": {"title": "AI bot setup", "price_string": "5000 RUB"}}}
    messages = [{"direction": "in", "content": {"text": "How much does it cost?"}}]

    prompt = build_prompt(chat, messages)

    assert "Known listing entry price: 5000 RUB" in prompt[1].content
    assert "Latest client asks about price or quote" in prompt[1].content
    assert "ask at most one missing detail" in prompt[1].content


def test_build_prompt_avoids_repeated_manager_deflection() -> None:
    chat = {"context": {"value": {"title": "AI bot setup", "price_string": "5000 RUB"}}}
    messages = [
        {"created": 1, "direction": "in", "content": {"text": "Need Telegram bot"}},
        {"created": 2, "direction": "out", "content": {"text": "Tell me functions and I will pass it to manager."}},
        {"created": 3, "direction": "in", "content": {"text": "Need CRM integration"}},
        {"created": 4, "direction": "out", "content": {"text": "I will pass it to manager after details."}},
        {"created": 5, "direction": "in", "content": {"text": "Need notifications once per day"}},
    ]

    prompt = build_prompt(chat, messages)

    assert "already mentioned manager handoff multiple times" in prompt[1].content
    assert "Do not repeat the same handoff sentence" in prompt[1].content
    assert "client has provided enough qualification details" in prompt[1].content


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
