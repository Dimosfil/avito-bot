import asyncio

from fastapi.testclient import TestClient
import pytest
import sqlite3

from app.assistant import AssistantDraft
from app import main as main_module
from app.main import app, manager_takeover_chat_ids


@pytest.fixture(autouse=True)
def clear_runtime_state(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "AUTOREPLY_PENDING_PATH", tmp_path / "autoreply-pending.json")
    monkeypatch.setattr(main_module, "AUTOREPLY_STATE_PATH", tmp_path / "autoreply-state.json")
    monkeypatch.setattr(main_module, "BOT_CONTROL_STATE_PATH", tmp_path / "bot-control-state.json")
    monkeypatch.setenv("AVITO_DATABASE_PATH", str(tmp_path / "avito-bot.sqlite3"))
    monkeypatch.setenv("AVITO_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("AVITO_LIVE_SYNC_ENABLED", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SHARED_DIR", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MANAGER_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_NOTIFY_TIMEOUT_SECONDS", raising=False)
    main_module.runtime_store = None
    main_module.runtime_store_key = None
    main_module.runtime_logger = None
    main_module.runtime_logger_key = None
    manager_takeover_chat_ids.clear()
    main_module.explicit_manager_takeover_chat_ids.clear()
    main_module.known_bot_control_chat_ids.clear()
    main_module.known_bot_control_item_keys.clear()
    main_module.bot_control_state_loaded = False
    main_module.bot_worker_enabled = False
    main_module.bot_worker_task = None
    main_module.backup_worker_task = None
    main_module.admin_logs.clear()
    main_module.bot_activity.update({"enabled": False, "running": False, "last_result": None, "last_error": None})
    yield
    manager_takeover_chat_ids.clear()
    main_module.explicit_manager_takeover_chat_ids.clear()
    main_module.known_bot_control_chat_ids.clear()
    main_module.known_bot_control_item_keys.clear()
    main_module.bot_control_state_loaded = False
    main_module.bot_worker_enabled = False
    main_module.bot_worker_task = None
    main_module.backup_worker_task = None
    main_module.runtime_store = None
    main_module.runtime_store_key = None
    main_module.runtime_logger = None
    main_module.runtime_logger_key = None
    main_module.admin_logs.clear()
    main_module.bot_activity.update({"enabled": False, "running": False, "last_result": None, "last_error": None})


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_storage_status_and_manual_backup() -> None:
    client = TestClient(app)

    status = client.get("/api/storage/status")
    backup = client.post("/api/storage/backup")

    assert status.status_code == 200
    assert status.json()["backend"] == "sqlite"
    assert backup.status_code == 200
    assert backup.json()["ok"] is True
    assert backup.json()["path"].endswith(".sqlite3")


def test_webhook_echo_storage() -> None:
    client = TestClient(app)

    response = client.post("/webhooks/avito/messenger", json={"type": "message", "value": {"id": "1"}})
    events = client.get("/api/webhooks/avito/events")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert events.status_code == 200
    assert events.json()["events"][0]["value"]["id"] == "1"


def test_cached_chats_and_messages_load_from_storage_without_avito(monkeypatch) -> None:
    class FailingAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            raise AssertionError("cached chats must not call Avito")

        async def get_chat(self, chat_id: str):
            raise AssertionError("cached chat must not call Avito")

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            raise AssertionError("cached messages must not call Avito")

    monkeypatch.setattr("app.main.AvitoClient", FailingAvitoClient)
    store = main_module.get_runtime_store()
    store.upsert_avito_chats([{"id": "chat-1", "updated": 10}])
    store.upsert_avito_messages(
        "chat-1",
        [{"id": "message-1", "created": 10, "direction": "in", "type": "text", "content": {"text": "hello"}}],
    )
    client = TestClient(app)

    chats = client.get("/api/avito/chats?refresh=false")
    chat = client.get("/api/avito/chats/chat-1?refresh=false")
    messages = client.get("/api/avito/chats/chat-1/messages?limit=50&refresh=false")

    assert chats.status_code == 200
    assert chats.json()["source"] == "cache"
    assert chats.json()["chats"][0]["id"] == "chat-1"
    assert chat.json()["source"] == "cache"
    assert messages.json()["source"] == "cache"
    assert messages.json()["messages"][0]["id"] == "message-1"


def test_process_unread_is_disabled_in_cache_only_mode(monkeypatch) -> None:
    monkeypatch.setenv("AVITO_LIVE_SYNC_ENABLED", "false")
    client = TestClient(app)

    response = client.post("/api/avito/process-unread")
    logs = client.get("/api/admin/logs")

    assert response.status_code == 409
    assert response.json()["detail"] == "Avito live sync is disabled; using PostgreSQL cache only"
    assert any(item["event"] == "live_sync_blocked" for item in logs.json()["logs"])


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


def test_qualified_buying_chats_are_persisted() -> None:
    client = TestClient(app)

    initial = client.get("/api/avito/qualified-buying-chats")
    saved = client.post(
        "/api/avito/qualified-buying-chats",
        json={"chat_ids": ["chat-2", "chat-1", "chat-1", ""]},
    )
    loaded = client.get("/api/avito/qualified-buying-chats")
    control = client.get("/api/avito/chats/chat-1/bot-control")

    assert initial.status_code == 200
    assert initial.json() == {"chat_ids": [], "count": 0}
    assert saved.status_code == 200
    assert saved.json() == {"chat_ids": ["chat-1", "chat-2"], "count": 2}
    assert loaded.json() == {"chat_ids": ["chat-1", "chat-2"], "count": 2}
    assert control.json() == {"chat_id": "chat-1", "manager_takeover": False, "bot_enabled": True}


def test_qualified_buying_chats_clear_legacy_auto_takeover() -> None:
    client = TestClient(app)
    main_module.get_runtime_store().set_state(
        "bot_control",
        {
            "known_chat_ids": ["chat-1"],
            "known_item_keys": [],
            "manager_takeover_chat_ids": ["chat-1"],
        },
    )
    main_module.bot_control_state_loaded = False

    saved = client.post("/api/avito/qualified-buying-chats", json={"chat_ids": ["chat-1"]})
    control = client.get("/api/avito/chats/chat-1/bot-control")

    assert saved.status_code == 200
    assert control.json() == {"chat_id": "chat-1", "manager_takeover": False, "bot_enabled": True}


def test_new_items_keep_ai_enabled_without_changing_existing(monkeypatch) -> None:
    class FakeAvitoClient:
        get_chats_calls = 0

        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            FakeAvitoClient.get_chats_calls += 1
            chats = [{"id": "chat-existing", "context": {"value": {"id": 1, "title": "Existing item"}}}]
            if FakeAvitoClient.get_chats_calls > 1:
                chats.append({"id": "chat-new-item", "context": {"value": {"id": 2, "title": "New item"}}})
            return {"chats": chats}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    client = TestClient(app)

    first_response = client.get("/api/avito/chats")
    existing_control = client.get("/api/avito/chats/chat-existing/bot-control")
    second_response = client.get("/api/avito/chats")
    new_control = client.get("/api/avito/chats/chat-new-item/bot-control")
    enabled_again = client.post("/api/avito/chats/chat-new-item/bot-control", json={"manager_takeover": False})

    assert first_response.status_code == 200
    assert existing_control.json() == {"chat_id": "chat-existing", "manager_takeover": False, "bot_enabled": True}
    assert second_response.status_code == 200
    assert new_control.json() == {"chat_id": "chat-new-item", "manager_takeover": False, "bot_enabled": True}
    assert enabled_again.json() == {"chat_id": "chat-new-item", "manager_takeover": False, "bot_enabled": True}


def test_new_chat_in_existing_item_keeps_ai_enabled(monkeypatch) -> None:
    class FakeAvitoClient:
        get_chats_calls = 0

        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            FakeAvitoClient.get_chats_calls += 1
            chats = [{"id": "chat-existing", "context": {"value": {"id": 1, "title": "Existing item"}}}]
            if FakeAvitoClient.get_chats_calls > 1:
                chats.append({"id": "chat-new", "context": {"value": {"id": 1, "title": "Existing item"}}})
            return {"chats": chats}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    client = TestClient(app)

    first_response = client.get("/api/avito/chats")
    second_response = client.get("/api/avito/chats")
    new_control = client.get("/api/avito/chats/chat-new/bot-control")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert new_control.json() == {"chat_id": "chat-new", "manager_takeover": False, "bot_enabled": True}


def test_chats_load_classifies_buying_intent_from_message_history(monkeypatch) -> None:
    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            return {
                "chats": [
                    {
                        "id": "chat-deal",
                        "context": {"value": {"id": 1, "title": "Existing item"}},
                        "last_message": {
                            "id": "out-1",
                            "direction": "out",
                            "content": {"text": "Добрый день, готова обсудить подробности"},
                        },
                    }
                ]
            }

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "in-1",
                        "created": 1,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "Договорились"},
                    },
                    {
                        "id": "out-1",
                        "created": 2,
                        "direction": "out",
                        "type": "text",
                        "content": {"text": "Добрый день, готова обсудить подробности"},
                    },
                ]
            }

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    client = TestClient(app)

    response = client.get("/api/avito/chats")
    qualified = client.get("/api/avito/qualified-buying-chats")
    control = client.get("/api/avito/chats/chat-deal/bot-control")

    assert response.status_code == 200
    assert response.json()["qualified_buying_chat_ids"] == ["chat-deal"]
    assert qualified.json()["chat_ids"] == ["chat-deal"]
    assert control.json() == {"chat_id": "chat-deal", "manager_takeover": False, "bot_enabled": True}


def test_manager_telegram_template_contains_context() -> None:
    text = main_module._format_manager_telegram_message(
        title="Нужен менеджер",
        chat={
            "id": "test-chat",
            "title": "Дмитрий",
            "context": {
                "value": {
                    "title": "AI-боты для бизнеса",
                    "url": "https://avito.test/item",
                }
            },
            "buyer": {"profile_url": "https://avito.test/user"},
        },
        chat_id="test-chat",
        message_text_value="готов купить",
        reason="готов купить",
    )

    assert "Нужен менеджер" in text
    assert "Канал: Avito" in text
    assert "Чат: test-chat" in text
    assert "Клиент: Дмитрий" in text
    assert "Объявление: AI-боты для бизнеса" in text
    assert "Причина: готов купить" in text
    assert "Последнее сообщение:\nготов купить" in text
    assert "Профиль клиента: https://avito.test/user" in text
    assert "Объявление Avito: https://avito.test/item" in text
    assert "Ссылка: http://127.0.0.1:8000/?chat=test-chat" in text


def test_item_stats_endpoint_forwards_request(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_item_stats(self, item_ids, date_from, date_to, period_grouping="day", fields=None):
            calls.append(
                {
                    "item_ids": item_ids,
                    "date_from": date_from,
                    "date_to": date_to,
                    "period_grouping": period_grouping,
                    "fields": fields,
                }
            )
            return {"result": {"items": [{"itemId": 123, "stats": [{"date": "2026-06-23", "uniqViews": 5}]}]}}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    client = TestClient(app)

    response = client.post(
        "/api/avito/item-stats",
        json={
            "item_ids": [123],
            "date_from": "2026-06-01",
            "date_to": "2026-06-23",
            "period_grouping": "day",
            "fields": ["uniqViews"],
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["items"][0]["stats"][0]["uniqViews"] == 5
    assert calls == [
        {
            "item_ids": [123],
            "date_from": "2026-06-01",
            "date_to": "2026-06-23",
            "period_grouping": "day",
            "fields": ["uniqViews"],
        }
    ]


def test_item_stats_endpoint_rejects_reversed_dates() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/avito/item-stats",
        json={"item_ids": [123], "date_from": "2026-06-23", "date_to": "2026-06-01"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "date_to must be greater than or equal to date_from"


def test_autoreply_start_requires_avito_credentials(monkeypatch) -> None:
    monkeypatch.delenv("AVITO_CLIENT_ID", raising=False)
    monkeypatch.delenv("AVITO_CLIENT_SECRET", raising=False)
    client = TestClient(app)

    response = client.post("/api/bot/autoreply/start")

    assert response.status_code == 400
    assert response.json()["detail"] == "AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required"


def test_autoreply_start_stop_persists_enabled_state(monkeypatch) -> None:
    async def fake_bot_worker_loop() -> None:
        return None

    monkeypatch.setenv("AVITO_CLIENT_ID", "client-id")
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr("app.main._bot_worker_loop", fake_bot_worker_loop)
    client = TestClient(app)

    started = client.post("/api/bot/autoreply/start")
    enabled_after_start = main_module._load_autoreply_enabled()
    stopped = client.post("/api/bot/autoreply/stop")

    assert started.status_code == 200
    assert started.json()["enabled"] is True
    assert enabled_after_start is True
    assert stopped.status_code == 200
    assert stopped.json()["enabled"] is False
    assert main_module._load_autoreply_enabled() is False


def test_autoreply_restore_enables_worker_by_default(monkeypatch) -> None:
    async def fake_bot_worker_loop() -> None:
        return None

    monkeypatch.setenv("AVITO_CLIENT_ID", "client-id")
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr("app.main._bot_worker_loop", fake_bot_worker_loop)

    asyncio.run(main_module._restore_bot_worker_state())

    assert main_module.bot_worker_enabled is True
    assert main_module.bot_activity["enabled"] is True
    assert main_module._load_autoreply_enabled() is True


def test_process_unread_sends_ai_reply(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []
    events: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            return {
                "chats": [
                    {
                        "id": "chat-1",
                        "title": "Дмитрий",
                        "context": {"value": {"title": "Test item", "url": "https://avito.test/item-1"}},
                    }
                ]
            }

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {"messages": [{"created": 1, "direction": "in", "type": "text", "content": {"text": "hello"}}]}

        async def send_text_message(self, chat_id: str, text: str):
            events.append("send")
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            events.append("read")
            read_chats.append(chat_id)
            return {}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            events.append("draft")
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
    assert events == ["read", "draft", "send"]


def test_process_unread_retries_pending_read_chat_after_restart(monkeypatch) -> None:
    events: list[str] = []

    class FakeAvitoClient:
        unread_calls = 0

        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            FakeAvitoClient.unread_calls += 1
            if FakeAvitoClient.unread_calls == 1:
                return {"chats": [{"id": "chat-1", "context": {"value": {"title": "Test item"}}}]}
            return {"chats": []}

        async def get_chat(self, chat_id: str):
            events.append("get_chat")
            return {"id": chat_id, "context": {"value": {"title": "Test item"}}}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "message-1",
                        "created": 1,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "hello"},
                    }
                ]
            }

        async def send_text_message(self, chat_id: str, text: str):
            events.append("send")
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            events.append("read")
            return {}

    class FakeAssistant:
        draft_calls = 0

        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            FakeAssistant.draft_calls += 1
            events.append("draft")
            if FakeAssistant.draft_calls == 1:
                raise RuntimeError("temporary draft failure")
            return AssistantDraft(text="reply text", handoff_required=False, handoff_reason=None)

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    client = TestClient(app)

    first_response = client.post("/api/avito/process-unread")
    second_response = client.post("/api/avito/process-unread")

    assert first_response.status_code == 200
    assert first_response.json()["processed"][0]["status"] == "failed"
    assert second_response.status_code == 200
    assert second_response.json()["processed"][0]["status"] == "sent"
    assert second_response.json()["sent_count"] == 1
    assert events == ["read", "draft", "get_chat", "draft", "send"]
    assert not main_module.AUTOREPLY_PENDING_PATH.exists()


def test_process_unread_clears_pending_when_manager_already_answered(monkeypatch) -> None:
    events: list[str] = []

    class FakeAvitoClient:
        unread_calls = 0

        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            FakeAvitoClient.unread_calls += 1
            if FakeAvitoClient.unread_calls == 1:
                return {"chats": [{"id": "chat-1"}]}
            return {"chats": []}

        async def get_chat(self, chat_id: str):
            events.append("get_chat")
            return {"id": chat_id}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            messages = [
                {
                    "id": "message-1",
                    "created": 1,
                    "direction": "in",
                    "type": "text",
                    "content": {"text": "hello"},
                }
            ]
            if FakeAvitoClient.unread_calls > 1:
                messages.append(
                    {
                        "id": "manager-1",
                        "created": 2,
                        "direction": "out",
                        "type": "text",
                        "content": {"text": "manager reply"},
                    }
                )
            return {"messages": messages}

        async def send_text_message(self, chat_id: str, text: str):
            events.append("send")
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            events.append("read")
            return {}

    class FakeAssistant:
        draft_calls = 0

        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            FakeAssistant.draft_calls += 1
            events.append("draft")
            raise RuntimeError("temporary draft failure")

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    client = TestClient(app)

    first_response = client.post("/api/avito/process-unread")
    second_response = client.post("/api/avito/process-unread")

    assert first_response.status_code == 200
    assert first_response.json()["processed"][0]["status"] == "failed"
    assert second_response.status_code == 200
    assert second_response.json()["processed"][0]["status"] == "answered"
    assert second_response.json()["sent_count"] == 0
    assert events == ["read", "draft", "get_chat"]
    assert not main_module.AUTOREPLY_PENDING_PATH.exists()


def test_process_unread_skips_manager_takeover_chat(monkeypatch) -> None:
    get_messages_calls: list[str] = []
    sent_messages: list[tuple[str, str]] = []
    telegram_messages: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            return {
                "chats": [
                    {
                        "id": "chat-1",
                        "title": "Дмитрий",
                        "context": {"value": {"title": "Test item", "url": "https://avito.test/item-1"}},
                    }
                ]
            }

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            get_messages_calls.append(chat_id)
            return {
                "messages": [
                    {"id": "message-1", "created": 1, "direction": "in", "type": "text", "content": {"text": "hello"}},
                    {"id": "message-2", "created": 2, "direction": "in", "type": "text", "content": {"text": "second"}},
                ]
            }

        async def send_text_message(self, chat_id: str, text: str):
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            raise AssertionError("AI must not draft replies for manager takeover chats")
            return AssistantDraft(text="reply text", handoff_required=False, handoff_reason=None)

    async def fake_send_telegram_notification(settings, text):
        telegram_messages.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    monkeypatch.setattr("app.main._send_telegram_notification", fake_send_telegram_notification)
    client = TestClient(app)
    client.post("/api/avito/chats/chat-1/bot-control", json={"manager_takeover": True})

    first_response = client.post("/api/avito/process-unread")
    second_response = client.post("/api/avito/process-unread")

    assert first_response.status_code == 200
    payload = first_response.json()
    assert payload["sent_count"] == 0
    assert payload["handoff_count"] == 0
    assert payload["processed"][0]["status"] == "manager_notified"
    assert second_response.status_code == 200
    assert second_response.json()["processed"][0]["status"] == "manager_active"
    assert get_messages_calls == ["chat-1", "chat-1"]
    assert sent_messages == []
    assert len(telegram_messages) == 1
    assert "second" in telegram_messages[0]
    assert "Канал: Avito" in telegram_messages[0]
    assert "Клиент: Дмитрий" in telegram_messages[0]
    assert "Объявление: Test item" in telegram_messages[0]
    assert "Ссылка: http://127.0.0.1:8000/?chat=chat-1" in telegram_messages[0]


def test_process_unread_answers_new_item_after_existing_baseline(monkeypatch) -> None:
    get_messages_calls: list[str] = []
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if unread_only:
                return {"chats": [{"id": "chat-new-item", "context": {"value": {"id": 2, "title": "New item"}}}]}
            return {"chats": [{"id": "chat-existing", "context": {"value": {"id": 1, "title": "Existing item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            get_messages_calls.append(chat_id)
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

    baseline = client.get("/api/avito/chats")
    response = client.post("/api/avito/process-unread")

    assert baseline.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_count"] == 1
    assert payload["processed"][0]["status"] == "sent"
    assert get_messages_calls == ["chat-existing", "chat-new-item"]
    assert read_chats == ["chat-new-item"]
    assert sent_messages == [("chat-new-item", "reply text")]


def test_process_unread_handles_new_chat_in_existing_item(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if unread_only:
                return {"chats": [{"id": "chat-new", "context": {"value": {"id": 1, "title": "Existing item"}}}]}
            return {"chats": [{"id": "chat-existing", "context": {"value": {"id": 1, "title": "Existing item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {"messages": [{"id": "message-1", "created": 1, "direction": "in", "type": "text", "content": {"text": "hello"}}]}

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

    baseline = client.get("/api/avito/chats")
    response = client.post("/api/avito/process-unread")

    assert baseline.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_count"] == 1
    assert payload["processed"][0]["status"] == "sent"
    assert read_chats == ["chat-new"]
    assert sent_messages == [("chat-new", "reply text")]


def test_process_unread_notifies_telegram_and_answers_qualified_buying_chat(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []
    telegram_messages: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            return {
                "chats": [
                    {
                        "id": "chat-qualified",
                        "title": "Олег",
                        "context": {"value": {"id": 1, "title": "Existing item", "url": "https://avito.test/item"}},
                    }
                ]
            }

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "message-qualified",
                        "created": 1,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "Когда можно созвониться?"},
                    }
                ]
            }

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

    async def fake_send_telegram_notification(settings, text):
        telegram_messages.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    monkeypatch.setattr("app.main._send_telegram_notification", fake_send_telegram_notification)
    client = TestClient(app)
    client.post("/api/avito/qualified-buying-chats", json={"chat_ids": ["chat-qualified"]})

    response = client.post("/api/avito/process-unread")

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"][0]["status"] == "sent"
    assert payload["sent_count"] == 1
    assert read_chats == ["chat-qualified"]
    assert sent_messages == [("chat-qualified", "reply text")]
    assert len(telegram_messages) == 1
    assert "Когда можно созвониться?" in telegram_messages[0]
    assert "Канал: Avito" in telegram_messages[0]
    assert "Клиент: Олег" in telegram_messages[0]
    assert "Объявление: Existing item" in telegram_messages[0]
    assert "Объявление Avito: https://avito.test/item" in telegram_messages[0]


def test_process_unread_skips_qualified_chat_after_manual_takeover(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []
    telegram_messages: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            return {"chats": [{"id": "chat-qualified", "context": {"value": {"id": 1, "title": "Existing item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "message-qualified",
                        "created": 1,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "Когда можно созвониться?"},
                    }
                ]
            }

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
            raise AssertionError("AI must not draft replies after manual takeover")

    async def fake_send_telegram_notification(settings, text):
        telegram_messages.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    monkeypatch.setattr("app.main._send_telegram_notification", fake_send_telegram_notification)
    client = TestClient(app)

    qualified = client.post("/api/avito/qualified-buying-chats", json={"chat_ids": ["chat-qualified"]})
    default_control = client.get("/api/avito/chats/chat-qualified/bot-control")
    manual_enabled = client.post("/api/avito/chats/chat-qualified/bot-control", json={"manager_takeover": True})
    response = client.post("/api/avito/process-unread")

    assert qualified.status_code == 200
    assert default_control.json() == {
        "chat_id": "chat-qualified",
        "manager_takeover": False,
        "bot_enabled": True,
    }
    assert manual_enabled.json() == {"chat_id": "chat-qualified", "manager_takeover": True, "bot_enabled": False}
    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"][0]["status"] == "manager_notified"
    assert payload["sent_count"] == 0
    assert read_chats == []
    assert sent_messages == []
    assert len(telegram_messages) == 1
    assert "Когда можно созвониться?" in telegram_messages[0]


def test_process_unread_scans_recent_read_chat_once(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []
    read_chats: list[str] = []
    events: list[str] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if unread_only:
                return {"chats": []}
            return {
                "chats": [
                    {
                        "id": "chat-read",
                        "updated": 9999999999,
                        "context": {"value": {"id": 1, "title": "Existing item"}},
                    }
                ]
            }

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "message-1",
                        "created": 9999999999,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "hello"},
                    }
                ]
            }

        async def send_text_message(self, chat_id: str, text: str):
            events.append("send")
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            events.append("read")
            read_chats.append(chat_id)
            return {}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            events.append("draft")
            return AssistantDraft(text="reply text", handoff_required=False, handoff_reason=None)

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    client = TestClient(app)

    first_response = client.post("/api/avito/process-unread")
    second_response = client.post("/api/avito/process-unread")

    assert first_response.status_code == 200
    assert first_response.json()["processed"][0]["status"] == "sent"
    assert first_response.json()["sent_count"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["processed"][0]["status"] == "already_processed"
    assert second_response.json()["sent_count"] == 0
    assert read_chats == ["chat-read"]
    assert sent_messages == [("chat-read", "reply text")]
    assert events == ["read", "draft", "send"]


def test_handoff_persists_qualified_chat_and_manager_action(monkeypatch, tmp_path) -> None:
    sent_messages: list[tuple[str, str]] = []
    notifications: list[dict[str, object]] = []

    class FakeAvitoClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False):
            if not unread_only:
                return {"chats": []}
            return {"chats": [{"id": "chat-handoff", "context": {"value": {"title": "Test item"}}}]}

        async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0):
            return {
                "messages": [
                    {
                        "id": "message-handoff",
                        "created": 1,
                        "direction": "in",
                        "type": "text",
                        "content": {"text": "готов купить"},
                    }
                ]
            }

        async def send_text_message(self, chat_id: str, text: str):
            sent_messages.append((chat_id, text))
            return {"id": "sent-1"}

        async def mark_chat_read(self, chat_id: str):
            return {}

    class FakeAssistant:
        def __init__(self, deepseek) -> None:
            self.deepseek = deepseek

        async def draft_reply(self, chat, messages):
            return AssistantDraft(
                text="Приняла, передам информацию менеджеру.",
                handoff_required=True,
                handoff_reason="готов купить",
            )

    async def fake_notify_manager_handoff(settings, *, chat, chat_id, handoff_reason, received_text):
        notifications.append(
            {
                "chat_id": chat_id,
                "chat_title": chat.get("context", {}).get("value", {}).get("title"),
                "handoff_reason": handoff_reason,
                "received_text": received_text,
            }
        )
        return {"status": "sent"}

    monkeypatch.setattr("app.main.AvitoClient", FakeAvitoClient)
    monkeypatch.setattr("app.main.DeepSeekClient", lambda settings: object())
    monkeypatch.setattr("app.main.SalesAssistant", FakeAssistant)
    monkeypatch.setattr("app.main._notify_manager_handoff", fake_notify_manager_handoff)
    client = TestClient(app)

    response = client.post("/api/avito/process-unread")
    qualified = client.get("/api/avito/qualified-buying-chats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent_count"] == 0
    assert payload["handoff_count"] == 1, payload
    assert payload["processed"][0]["status"] == "handoff_required"
    assert payload["processed"][0]["sent_message_id"] == "sent-1"
    assert qualified.json()["chat_ids"] == ["chat-handoff"]
    assert sent_messages == [("chat-handoff", "Приняла, передам информацию менеджеру.")]
    assert notifications == [
        {
            "chat_id": "chat-handoff",
            "chat_title": "Test item",
            "handoff_reason": "готов купить",
            "received_text": "готов купить",
        }
    ]

    with sqlite3.connect(tmp_path / "avito-bot.sqlite3") as con:
        row = con.execute(
            "SELECT action_type, payload_json FROM manager_actions WHERE external_chat_id = ?",
            ("chat-handoff",),
        ).fetchone()
    assert row is not None
    assert row[0] == "handoff_required"
    assert "готов купить" in row[1]
