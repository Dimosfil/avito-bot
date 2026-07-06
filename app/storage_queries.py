from __future__ import annotations

from typing import Final


APPLICATION_TABLES: Final[tuple[str, ...]] = (
    "app_meta",
    "runtime_state",
    "conversations",
    "messages",
    "manager_actions",
)

SQLITE_SCHEMA: Final[str] = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    external_item_key TEXT,
    title TEXT,
    payload_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(channel, external_chat_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    message_key TEXT NOT NULL,
    external_message_id TEXT,
    direction TEXT,
    message_type TEXT,
    author_role TEXT,
    created_at INTEGER,
    text TEXT,
    payload_json TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    UNIQUE(channel, external_chat_id, message_key)
);
CREATE TABLE IF NOT EXISTS manager_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
"""

POSTGRES_SCHEMA: Final[tuple[str, ...]] = (
    """
    CREATE TABLE IF NOT EXISTS app_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_state (
        key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        updated_at BIGINT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id BIGSERIAL PRIMARY KEY,
        channel TEXT NOT NULL,
        external_chat_id TEXT NOT NULL,
        external_item_key TEXT,
        title TEXT,
        payload_json TEXT NOT NULL,
        updated_at BIGINT NOT NULL,
        UNIQUE(channel, external_chat_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        channel TEXT NOT NULL,
        external_chat_id TEXT NOT NULL,
        message_key TEXT NOT NULL,
        external_message_id TEXT,
        direction TEXT,
        message_type TEXT,
        author_role TEXT,
        created_at BIGINT,
        text TEXT,
        payload_json TEXT NOT NULL,
        received_at BIGINT NOT NULL,
        UNIQUE(channel, external_chat_id, message_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manager_actions (
        id BIGSERIAL PRIMARY KEY,
        channel TEXT NOT NULL,
        external_chat_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at BIGINT NOT NULL
    )
    """,
)

SQLITE_SET_SCHEMA_VERSION: Final[str] = """
INSERT OR REPLACE INTO app_meta(key, value) VALUES('schema_version', ?)
"""

POSTGRES_SET_SCHEMA_VERSION: Final[str] = """
INSERT INTO app_meta(key, value) VALUES('schema_version', %s)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""

SQLITE_GET_STATE: Final[str] = "SELECT value_json FROM runtime_state WHERE key = ?"
POSTGRES_GET_STATE: Final[str] = "SELECT value_json FROM runtime_state WHERE key = %s"

SQLITE_SET_STATE: Final[str] = """
INSERT INTO runtime_state(key, value_json, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(key) DO UPDATE
SET value_json = excluded.value_json, updated_at = excluded.updated_at
"""

POSTGRES_SET_STATE: Final[str] = """
INSERT INTO runtime_state(key, value_json, updated_at)
VALUES (%s, %s, %s)
ON CONFLICT (key) DO UPDATE
SET value_json = EXCLUDED.value_json, updated_at = EXCLUDED.updated_at
"""

SQLITE_UPSERT_CONVERSATION: Final[str] = """
INSERT INTO conversations(channel, external_chat_id, external_item_key, title, payload_json, updated_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(channel, external_chat_id) DO UPDATE
SET external_item_key = excluded.external_item_key,
    title = excluded.title,
    payload_json = excluded.payload_json,
    updated_at = excluded.updated_at
"""

POSTGRES_UPSERT_CONVERSATION: Final[str] = """
INSERT INTO conversations(channel, external_chat_id, external_item_key, title, payload_json, updated_at)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (channel, external_chat_id) DO UPDATE
SET external_item_key = EXCLUDED.external_item_key,
    title = EXCLUDED.title,
    payload_json = EXCLUDED.payload_json,
    updated_at = EXCLUDED.updated_at
"""

SQLITE_UPSERT_MESSAGE: Final[str] = """
INSERT INTO messages(
    channel, external_chat_id, message_key, external_message_id, direction,
    message_type, author_role, created_at, text, payload_json, received_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(channel, external_chat_id, message_key) DO UPDATE
SET external_message_id = excluded.external_message_id,
    direction = excluded.direction,
    message_type = excluded.message_type,
    author_role = excluded.author_role,
    created_at = excluded.created_at,
    text = excluded.text,
    payload_json = excluded.payload_json,
    received_at = excluded.received_at
"""

POSTGRES_UPSERT_MESSAGE: Final[str] = """
INSERT INTO messages(
    channel, external_chat_id, message_key, external_message_id, direction,
    message_type, author_role, created_at, text, payload_json, received_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (channel, external_chat_id, message_key) DO UPDATE
SET external_message_id = EXCLUDED.external_message_id,
    direction = EXCLUDED.direction,
    message_type = EXCLUDED.message_type,
    author_role = EXCLUDED.author_role,
    created_at = EXCLUDED.created_at,
    text = EXCLUDED.text,
    payload_json = EXCLUDED.payload_json,
    received_at = EXCLUDED.received_at
"""

SQLITE_LIST_CHATS: Final[str] = """
SELECT external_chat_id, payload_json
FROM conversations
WHERE channel = ?
ORDER BY updated_at DESC, id DESC
LIMIT ? OFFSET ?
"""

POSTGRES_LIST_CHATS: Final[str] = """
SELECT external_chat_id, payload_json
FROM conversations
WHERE channel = %s
ORDER BY updated_at DESC, id DESC
LIMIT %s OFFSET %s
"""

SQLITE_GET_CHAT: Final[str] = """
SELECT payload_json
FROM conversations
WHERE channel = ? AND external_chat_id = ?
"""

POSTGRES_GET_CHAT: Final[str] = """
SELECT payload_json
FROM conversations
WHERE channel = %s AND external_chat_id = %s
"""

SQLITE_LIST_MESSAGES: Final[str] = """
SELECT payload_json
FROM (
    SELECT payload_json, COALESCE(created_at, received_at) AS sort_at, id
    FROM messages
    WHERE channel = ? AND external_chat_id = ?
    ORDER BY sort_at DESC, id DESC
    LIMIT ? OFFSET ?
) latest
ORDER BY sort_at ASC, id ASC
"""

POSTGRES_LIST_MESSAGES: Final[str] = """
SELECT payload_json
FROM (
    SELECT payload_json, COALESCE(created_at, received_at) AS sort_at, id
    FROM messages
    WHERE channel = %s AND external_chat_id = %s
    ORDER BY sort_at DESC, id DESC
    LIMIT %s OFFSET %s
) latest
ORDER BY sort_at ASC, id ASC
"""

SQLITE_INSERT_MANAGER_ACTION: Final[str] = """
INSERT INTO manager_actions(channel, external_chat_id, action_type, payload_json, created_at)
VALUES (?, ?, ?, ?, ?)
"""

POSTGRES_INSERT_MANAGER_ACTION: Final[str] = """
INSERT INTO manager_actions(channel, external_chat_id, action_type, payload_json, created_at)
VALUES (%s, %s, %s, %s, %s)
"""

SQLITE_IMPORT_APP_META: Final[str] = """
INSERT INTO app_meta(key, value) VALUES (?, ?)
ON CONFLICT(key) DO UPDATE SET value = excluded.value
"""

POSTGRES_IMPORT_APP_META: Final[str] = """
INSERT INTO app_meta(key, value) VALUES (%s, %s)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""

SQLITE_IMPORT_STATE = SQLITE_SET_STATE
POSTGRES_IMPORT_STATE = POSTGRES_SET_STATE

SQLITE_IMPORT_CONVERSATION: Final[str] = """
INSERT INTO conversations(id, channel, external_chat_id, external_item_key, title, payload_json, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(channel, external_chat_id) DO UPDATE
SET external_item_key = excluded.external_item_key,
    title = excluded.title,
    payload_json = excluded.payload_json,
    updated_at = excluded.updated_at
"""

POSTGRES_IMPORT_CONVERSATION: Final[str] = """
INSERT INTO conversations(
    id, channel, external_chat_id, external_item_key, title, payload_json, updated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (channel, external_chat_id) DO UPDATE
SET external_item_key = EXCLUDED.external_item_key,
    title = EXCLUDED.title,
    payload_json = EXCLUDED.payload_json,
    updated_at = EXCLUDED.updated_at
"""

SQLITE_IMPORT_MESSAGE: Final[str] = """
INSERT INTO messages(
    id, channel, external_chat_id, message_key, external_message_id, direction,
    message_type, author_role, created_at, text, payload_json, received_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(channel, external_chat_id, message_key) DO UPDATE
SET external_message_id = excluded.external_message_id,
    direction = excluded.direction,
    message_type = excluded.message_type,
    author_role = excluded.author_role,
    created_at = excluded.created_at,
    text = excluded.text,
    payload_json = excluded.payload_json,
    received_at = excluded.received_at
"""

POSTGRES_IMPORT_MESSAGE: Final[str] = """
INSERT INTO messages(
    id, channel, external_chat_id, message_key, external_message_id, direction,
    message_type, author_role, created_at, text, payload_json, received_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (channel, external_chat_id, message_key) DO UPDATE
SET external_message_id = EXCLUDED.external_message_id,
    direction = EXCLUDED.direction,
    message_type = EXCLUDED.message_type,
    author_role = EXCLUDED.author_role,
    created_at = EXCLUDED.created_at,
    text = EXCLUDED.text,
    payload_json = EXCLUDED.payload_json,
    received_at = EXCLUDED.received_at
"""

SQLITE_IMPORT_MANAGER_ACTION: Final[str] = """
INSERT INTO manager_actions(id, channel, external_chat_id, action_type, payload_json, created_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE
SET channel = excluded.channel,
    external_chat_id = excluded.external_chat_id,
    action_type = excluded.action_type,
    payload_json = excluded.payload_json,
    created_at = excluded.created_at
"""

POSTGRES_IMPORT_MANAGER_ACTION: Final[str] = """
INSERT INTO manager_actions(id, channel, external_chat_id, action_type, payload_json, created_at)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE
SET channel = EXCLUDED.channel,
    external_chat_id = EXCLUDED.external_chat_id,
    action_type = EXCLUDED.action_type,
    payload_json = EXCLUDED.payload_json,
    created_at = EXCLUDED.created_at
"""


def export_table_query(table: str) -> str:
    if table not in APPLICATION_TABLES:
        raise ValueError(f"Unsupported runtime storage table: {table}")
    return f"SELECT * FROM {table} ORDER BY 1"


def postgres_sync_sequence_query(table: str) -> str:
    if table not in {"conversations", "messages", "manager_actions"}:
        raise ValueError(f"Unsupported sequence table: {table}")
    return f"""
    SELECT setval(
        pg_get_serial_sequence(%s, %s),
        COALESCE((SELECT MAX(id) FROM {table}), 1),
        EXISTS(SELECT 1 FROM {table})
    )
    """
