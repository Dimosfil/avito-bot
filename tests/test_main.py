from fastapi.testclient import TestClient
import pytest

from app.assistant import AssistantDraft
from app.main import app, manager_takeover_chat_ids


@pytest.fixture(autouse=True)
def clear_manager_takeovers():
    manager_takeover_chat_ids.clear()
    yield
    manager_takeover_chat_ids.clear()


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_echo_storage() -> None:
    client = TestClient(app)

    response = client.post("/webhooks/avito/messenger", json={"type": "message", "value": {"id": "1"}})
    events = client.get("/api/webhooks/avito/events")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert events.status_code == 200
    assert events.json()["events"][0]["value"]["id"] == "1"


def test_chat_bot_control_roundtrip() -> None:
    client = TestClient(app)

    initial = client.get("/api/avito/chats/chat-1/bot-control")
    enabled = client.post("/api/avito/chats/chat-1/bot-control", json={"manager_takeover": True})
    disabled = client.post("/api/avito/chats/chat-1/bot-control", json={"manager_takeover": False})

    assert initial.status_code == 200
    assert initial.json()["bot_enabled"] is True
    assert enabled.status_code == 200
    assert enabled.json() == {"chat_id": "chat-1", "manager_takeover": True, "bot_enabled": False}
    assert disabled.status_code == 200
    assert disabled.json() == {"chat_id": "chat-1", "manager_takeover": False, "bot_enabled": True}


def test_process_unread_sends_ai_reply(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            assert unread_only is True
            return {"chats": [{"id": "chat-1", "context": {"value": {"title": "Test item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {"messages": [{"created": 1, "direction": "in", "type": "text", "content": {"text": "hello"}}]}

        async def send_text_message(self, chat_id: str, text: str):
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            read_chats.append(chat_id)
            return {}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            return AssistantDraft(text="reply text", handoff_required=False, handoff_reason=None)

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    client = TestClient(app)

    response = client.post("/api/avito/process-unread")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_count"] == 1
    assert payload["processed"][0]["status"] == "sent"
    assert payload["processed"][0]["estimate_seconds"] >= 8
    assert payload["processed"][0]["accepted_at"] is not None
    assert payload["processed"][0]["estimated_reply_at"] is not None
    assert payload["processed"][0]["sent_at"] is not None
    assert payload["processed"][0]["duration_ms"] >= 0
    assert sent_messages == [("chat-1", "reply text")]
    assert read_chats == ["chat-1"]


def test_process_unread_skips_manager_takeover_chat(monkeypatch) -> None:
    get_messages_calls: list[str] = []
    sent_messages: list[tuple[str, str]] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            assert unread_only is True
            return {"chats": [{"id": "chat-1", "context": {"value": {"title": "Test item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            get_messages_calls.append(chat_id)
            return {"messages": [{"created": 1, "direction": "in", "type": "text", "content": {"text": "hello"}}]}

        async def send_text_message(self, chat_id: str, text: str):
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            return AssistantDraft(text="reply text", handoff_required=False, handoff_reason=None)

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    client = TestClient(app)
    client.post("/api/avito/chats/chat-1/bot-control", json={"manager_takeover": True})

    response = client.post("/api/avito/process-unread")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_count"] == 0
    assert payload["handoff_count"] == 0
    assert payload["processed"][0]["status"] == "manager_active"
    assert get_messages_calls == []
    assert sent_messages == []
