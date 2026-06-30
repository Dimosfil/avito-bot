from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import Settings


SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class BackupResult:
    backend: str
    path: Path
    bytes: int
    created_at: int


class RuntimeStore:
    def __init__(self, *, database_url: str | None, sqlite_path: Path | None, backup_dir: Path) -> None:
        if database_url and sqlite_path:
            raise ValueError("Use either database_url or sqlite_path, not both")
        self.database_url = database_url
        self.sqlite_path = sqlite_path
        self.backup_dir = backup_dir
        self.backend = "postgres" if database_url and _is_postgres_url(database_url) else "sqlite"
        if self.backend == "sqlite" and sqlite_path is None:
            self.sqlite_path = _sqlite_path_from_url(database_url) if database_url else None
        if self.backend == "sqlite" and self.sqlite_path is None:
            raise ValueError("sqlite_path is required for SQLite storage")
        if database_url and not (_is_postgres_url(database_url) or database_url.startswith("sqlite:")):
            raise ValueError("DATABASE_URL must start with postgresql://, postgres://, or sqlite:///")

    @classmethod
    def from_settings(cls, settings: Settings, *, root: Path, runtime_dir: Path) -> "RuntimeStore":
        backup_dir = resolve_backup_dir(settings, runtime_dir)
        if settings.database_url:
            return cls(database_url=settings.database_url, sqlite_path=None, backup_dir=backup_dir)
        return cls(database_url=None, sqlite_path=resolve_sqlite_path(settings, runtime_dir), backup_dir=backup_dir)

    def cache_key(self) -> tuple[str, str, str]:
        return (self.backend, str(self.database_url or self.sqlite_path), str(self.backup_dir))

    def ensure_schema(self) -> None:
        if self.backend == "postgres":
            self._ensure_postgres_schema()
            return
        assert self.sqlite_path is not None
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as con:
            con.executescript(
                """
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
            )
            con.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    def get_state(self, key: str) -> Any | None:
        self.ensure_schema()
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute("SELECT value_json FROM runtime_state WHERE key = %s", (key,))
                    row = cur.fetchone()
            return json.loads(row[0]) if row else None
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            row = con.execute("SELECT value_json FROM runtime_state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_state(self, key: str, value: Any) -> None:
        self.ensure_schema()
        payload = json.dumps(value, ensure_ascii=False)
        updated_at = int(time.time())
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO runtime_state(key, value_json, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (key) DO UPDATE
                        SET value_json = EXCLUDED.value_json, updated_at = EXCLUDED.updated_at
                        """,
                        (key, payload, updated_at),
                    )
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.execute(
                """
                INSERT INTO runtime_state(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (key, payload, updated_at),
            )

    def upsert_avito_chats(self, chats: list[dict[str, Any]]) -> None:
        self.ensure_schema()
        rows = [_chat_row(chat) for chat in chats if chat.get("id")]
        if not rows:
            return
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for row in rows:
                        cur.execute(
                            """
                            INSERT INTO conversations(channel, external_chat_id, external_item_key, title, payload_json, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (channel, external_chat_id) DO UPDATE
                            SET external_item_key = EXCLUDED.external_item_key,
                                title = EXCLUDED.title,
                                payload_json = EXCLUDED.payload_json,
                                updated_at = EXCLUDED.updated_at
                            """,
                            row,
                        )
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.executemany(
                """
                INSERT INTO conversations(channel, external_chat_id, external_item_key, title, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel, external_chat_id) DO UPDATE
                SET external_item_key = excluded.external_item_key,
                    title = excluded.title,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def upsert_avito_messages(self, chat_id: str, messages: list[dict[str, Any]]) -> None:
        self.ensure_schema()
        rows = [_message_row(chat_id, message) for message in messages]
        if not rows:
            return
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for row in rows:
                        cur.execute(
                            """
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
                            """,
                            row,
                        )
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.executemany(
                """
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
                """,
                rows,
            )

    def record_manager_action(self, chat_id: str, action_type: str, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        row = ("avito", chat_id, action_type, json.dumps(payload, ensure_ascii=False), int(time.time()))
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO manager_actions(channel, external_chat_id, action_type, payload_json, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        row,
                    )
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.execute(
                """
                INSERT INTO manager_actions(channel, external_chat_id, action_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                row,
            )

    def create_backup(self, *, keep: int = 14) -> BackupResult:
        self.ensure_schema()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        created_at = int(time.time())
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(created_at))
        if self.backend == "postgres":
            backup_path = self.backup_dir / f"avito-bot-{stamp}.json"
            self._export_json_backup(backup_path)
        else:
            assert self.sqlite_path is not None
            backup_path = self.backup_dir / f"avito-bot-{stamp}.sqlite3"
            temp_path = backup_path.with_suffix(".sqlite3.tmp")
            source = sqlite3.connect(self.sqlite_path)
            target = sqlite3.connect(temp_path)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
            temp_path.replace(backup_path)
        self.prune_backups(keep)
        return BackupResult(
            backend=self.backend,
            path=backup_path,
            bytes=backup_path.stat().st_size,
            created_at=created_at,
        )

    def prune_backups(self, keep: int = 14) -> None:
        if keep <= 0 or not self.backup_dir.exists():
            return
        backups = sorted(
            [
                path
                for path in self.backup_dir.glob("avito-bot-*")
                if path.suffix in {".sqlite3", ".json"}
            ],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old_path in backups[keep:]:
            try:
                old_path.unlink()
            except OSError:
                pass

    def status(self) -> dict[str, object]:
        self.ensure_schema()
        data: dict[str, object] = {
            "backend": self.backend,
            "backup_dir": str(self.backup_dir),
        }
        if self.backend == "sqlite":
            assert self.sqlite_path is not None
            data.update(
                {
                    "database_path": str(self.sqlite_path),
                    "database_exists": self.sqlite_path.exists(),
                    "database_bytes": self.sqlite_path.stat().st_size if self.sqlite_path.exists() else 0,
                }
            )
        else:
            data["database_url_configured"] = True
        latest = self.latest_backup()
        data["latest_backup"] = str(latest) if latest else None
        return data

    def latest_backup(self) -> Path | None:
        if not self.backup_dir.exists():
            return None
        backups = [path for path in self.backup_dir.glob("avito-bot-*") if path.suffix in {".sqlite3", ".json"}]
        return max(backups, key=lambda path: path.stat().st_mtime) if backups else None

    def _ensure_postgres_schema(self) -> None:
        with self._postgres_connection() as con:
            with con.cursor() as cur:
                for statement in POSTGRES_SCHEMA:
                    cur.execute(statement)
                cur.execute(
                    """
                    INSERT INTO app_meta(key, value) VALUES('schema_version', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    (SCHEMA_VERSION,),
                )

    def _postgres_connection(self):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on deployment env
            raise RuntimeError("PostgreSQL storage requires psycopg. Run dependency install after updating pyproject.") from exc
        assert self.database_url is not None
        return psycopg.connect(self.database_url)

    def _export_json_backup(self, backup_path: Path) -> None:
        export: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "created_at": int(time.time()), "tables": {}}
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for table in ("app_meta", "runtime_state", "conversations", "messages", "manager_actions"):
                        cur.execute(f"SELECT * FROM {table}")
                        columns = [column.name for column in cur.description]
                        export["tables"][table] = [dict(zip(columns, row)) for row in cur.fetchall()]
        else:
            assert self.sqlite_path is not None
            with sqlite3.connect(self.sqlite_path) as con:
                con.row_factory = sqlite3.Row
                for table in ("app_meta", "runtime_state", "conversations", "messages", "manager_actions"):
                    export["tables"][table] = [dict(row) for row in con.execute(f"SELECT * FROM {table}")]
        temp_path = backup_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(backup_path)


POSTGRES_SCHEMA = [
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
]


def resolve_sqlite_path(settings: Settings, runtime_dir: Path) -> Path:
    if settings.avito_database_path:
        return Path(settings.avito_database_path)
    shared_dir = settings.shared_dir or os.getenv("SHARED_DIR")
    if shared_dir:
        return Path(shared_dir) / "avito-bot" / "avito-bot.sqlite3"
    return runtime_dir / "avito-bot.sqlite3"


def resolve_backup_dir(settings: Settings, runtime_dir: Path) -> Path:
    if settings.avito_backup_dir:
        return Path(settings.avito_backup_dir)
    shared_dir = settings.shared_dir or os.getenv("SHARED_DIR")
    if shared_dir:
        return Path(shared_dir) / "avito-bot" / "backups"
    return runtime_dir / "backups"


def _is_postgres_url(database_url: str) -> bool:
    return database_url.startswith("postgresql://") or database_url.startswith("postgres://")


def _sqlite_path_from_url(database_url: str | None) -> Path | None:
    if not database_url:
        return None
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return None
    path = parsed.path
    if os.name == "nt" and path.startswith("/") and len(path) > 3 and path[2] == ":":
        path = path[1:]
    return Path(path)


def _chat_row(chat: dict[str, Any]) -> tuple[str, str, str | None, str | None, str, int]:
    chat_id = str(chat.get("id"))
    item = _chat_item_context(chat)
    title = str(chat.get("title") or item.get("title") or "") or None
    item_key = _chat_item_key(chat) or None
    return ("avito", chat_id, item_key, title, json.dumps(chat, ensure_ascii=False), int(time.time()))


def _message_row(chat_id: str, message: dict[str, Any]) -> tuple[Any, ...]:
    message_id = message.get("id") or message.get("message_id")
    message_key = str(message_id) if message_id else _stable_message_key(message)
    direction = message.get("direction")
    message_type = message.get("type")
    author_role = _author_role(direction)
    created_at = _safe_int(message.get("created") or message.get("created_at"))
    text = _message_text(message)
    return (
        "avito",
        chat_id,
        message_key,
        str(message_id) if message_id else None,
        str(direction) if direction else None,
        str(message_type) if message_type else None,
        author_role,
        created_at,
        text,
        json.dumps(message, ensure_ascii=False),
        int(time.time()),
    )


def _stable_message_key(message: dict[str, Any]) -> str:
    payload = json.dumps(message, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _message_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _author_role(direction: Any) -> str | None:
    if direction == "in":
        return "client"
    if direction == "out":
        return "seller"
    return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chat_item_key(chat: dict[str, Any]) -> str:
    item = _chat_item_context(chat)
    value = (
        item.get("id")
        or item.get("item_id")
        or item.get("avito_id")
        or chat.get("item_id")
        or chat.get("itemId")
        or item.get("url")
        or item.get("uri")
        or item.get("link")
        or item.get("external_url")
    )
    if value:
        return str(value)
    title = item.get("title") or chat.get("context", {}).get("title") or ""
    price = item.get("price_string") or ""
    fallback = f"{title}|{price}".strip("|")
    return fallback or ""


def _chat_item_context(chat: dict[str, Any]) -> dict[str, Any]:
    context = chat.get("context")
    if isinstance(context, dict) and isinstance(context.get("value"), dict):
        return context["value"]
    item = chat.get("item")
    if isinstance(item, dict):
        return item
    return {}
