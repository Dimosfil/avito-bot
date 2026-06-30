from app.avito_payload import author_role, chat_item_context, chat_item_key, message_text, safe_int


def test_chat_item_context_prefers_avito_context_value() -> None:
    chat = {
        "context": {"value": {"id": 123, "title": "Context item"}},
        "item": {"id": 456, "title": "Fallback item"},
    }

    assert chat_item_context(chat) == {"id": 123, "title": "Context item"}
    assert chat_item_key(chat) == "123"


def test_chat_item_key_falls_back_to_title_and_price() -> None:
    chat = {"context": {"value": {"title": "Bot setup", "price_string": "5000"}}}

    assert chat_item_key(chat) == "Bot setup|5000"


def test_message_text_extracts_only_non_empty_text() -> None:
    assert message_text({"content": {"text": "  hello  "}}) == "hello"
    assert message_text({"content": {"text": "   "}}) is None
    assert message_text({"content": {"image": {"url": "https://example.test/image.jpg"}}}) is None


def test_author_role_maps_avito_directions() -> None:
    assert author_role("in") == "client"
    assert author_role("out") == "seller"
    assert author_role("system") is None


def test_safe_int_handles_external_payload_values() -> None:
    assert safe_int("42") == 42
    assert safe_int(None) is None
    assert safe_int("not-a-number") is None
