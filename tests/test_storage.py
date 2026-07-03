import sqlite3

from app.config import Settings
from app.storage import RuntimeStore, resolve_backup_dir, resolve_sqlite_path


def test_sqlite_store_persists_runtime_state_and_avito_payloads(tmp_path) -> None:
    store = RuntimeStore(database_url=None, sqlite_path=tmp_path / "state.sqlite3", backup_dir=tmp_path / "backups")
    store.ensure_schema()

    store.set_state("autoreply_enabled", True)
    store.upsert_avito_chats([{"id": "chat-1", "context": {"value": {"id": 123, "title": "Item"}}}])
    store.upsert_avito_messages(
        "chat-1",
        [{"id": "message-1", "created": 10, "direction": "in", "type": "text", "content": {"text": "hello"}}],
    )

    assert store.get_state("autoreply_enabled") is True
    with sqlite3.connect(tmp_path / "state.sqlite3") as con:
        assert con.execute("SELECT external_chat_id FROM conversations").fetchone()[0] == "chat-1"
        assert con.execute("SELECT text FROM messages").fetchone()[0] == "hello"


def test_sqlite_backup_uses_consistent_copy(tmp_path) -> None:
    store = RuntimeStore(database_url=None, sqlite_path=tmp_path / "state.sqlite3", backup_dir=tmp_path / "backups")
    store.set_state("bot_control", {"manager_takeover_chat_ids": ["chat-1"]})

    result = store.create_backup()

    assert result.backend == "sqlite"
    assert result.path.exists()
    assert result.bytes > 0


def test_runtime_store_import_data_preserves_rows_without_duplicates(tmp_path) -> None:
    source = RuntimeStore(database_url=None, sqlite_path=tmp_path / "source.sqlite3", backup_dir=tmp_path / "backups")
    target = RuntimeStore(database_url=None, sqlite_path=tmp_path / "target.sqlite3", backup_dir=tmp_path / "backups")

    source.set_state("autoreply_enabled", True)
    source.upsert_avito_chats([{"id": "chat-1", "context": {"value": {"id": 123, "title": "Item"}}}])
    source.upsert_avito_messages(
        "chat-1",
        [{"id": "message-1", "created": 10, "direction": "in", "type": "text", "content": {"text": "hello"}}],
    )
    source.record_manager_action("chat-1", "takeover", {"enabled": True})

    export = source.export_data()
    assert target.import_data(export) == {
        "app_meta": 1,
        "runtime_state": 1,
        "conversations": 1,
        "messages": 1,
        "manager_actions": 1,
    }
    target.import_data(export)

    assert target.get_state("autoreply_enabled") is True
    with sqlite3.connect(tmp_path / "target.sqlite3") as con:
        assert con.execute("SELECT count(*) FROM conversations").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM manager_actions").fetchone()[0] == 1


def test_sqlite_store_lists_cached_avito_chats_and_messages(tmp_path) -> None:
    store = RuntimeStore(database_url=None, sqlite_path=tmp_path / "state.sqlite3", backup_dir=tmp_path / "backups")
    store.upsert_avito_chats([{"id": "chat-1", "updated": 10, "last_message": {"direction": "in", "read": False}}])
    store.upsert_avito_messages(
        "chat-1",
        [{"id": "message-1", "created": 10, "direction": "in", "type": "text", "content": {"text": "hello"}}],
    )

    chats = store.list_avito_chats(unread_only=True)
    messages = store.list_avito_messages("chat-1")

    assert chats[0]["id"] == "chat-1"
    assert messages[0]["id"] == "message-1"


def test_shared_dir_defaults_for_sqlite_and_backups(tmp_path) -> None:
    settings = Settings(
        avito_client_id=None,
        avito_client_secret=None,
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="deepseek",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        codex_app_server_base_url=None,
        codex_app_server_api_key=None,
        codex_app_server_model="codex",
        shared_dir=str(tmp_path / "shared"),
    )

    assert resolve_sqlite_path(settings, tmp_path / ".codex-runtime") == tmp_path / "shared" / "avito-bot" / "avito-bot.sqlite3"
    assert resolve_backup_dir(settings, tmp_path / ".codex-runtime") == tmp_path / "shared" / "avito-bot" / "backups"
