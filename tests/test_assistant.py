from app import bot_rules
from app.assistant import build_prompt, detect_handoff


def test_detect_handoff_for_commercial_proposal() -> None:
    messages = [
        {
            "direction": "in",
            "content": {"text": "Здравствуйте, хочу КП по этому товару"},
        }
    ]

    assert detect_handoff(messages) == "хочу кп"


def test_build_prompt_includes_item_context() -> None:
    chat = {"context": {"value": {"title": "Test item", "price_string": "1000 ₽", "url": "https://example.test"}}}
    messages = [{"direction": "in", "content": {"text": "Здравствуйте"}}]

    prompt = build_prompt(chat, messages)

    assert "Test item" in prompt[1].content
    assert "client: Здравствуйте" in prompt[1].content


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

    assert "The seller account is Oksana" in prompt[0].content
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
