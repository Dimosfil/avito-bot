from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from app import storage_queries as sql
from app.avito_payload import author_role, chat_item_context, chat_item_key, message_text, safe_int
from app.config import Settings
from app.storage_queries import APPLICATION_TABLES


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
        self._schema_ready = False
        self._postgres_lock = threading.RLock()
        self._postgres_con: Any | None = None
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
        if self._schema_ready:
            return
        if self.backend == "postgres":
            self._ensure_postgres_schema()
            self._schema_ready = True
            return
        assert self.sqlite_path is not None
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as con:
            con.executescript(sql.SQLITE_SCHEMA)
            con.execute(sql.SQLITE_SET_SCHEMA_VERSION, (SCHEMA_VERSION,))
        self._schema_ready = True

    def get_state(self, key: str) -> Any | None:
        self.ensure_schema()
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_GET_STATE, (key,))
                    row = cur.fetchone()
            return json.loads(row[0]) if row else None
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            row = con.execute(sql.SQLITE_GET_STATE, (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_state(self, key: str, value: Any) -> None:
        self.ensure_schema()
        payload = json.dumps(value, ensure_ascii=False)
        updated_at = int(time.time())
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_SET_STATE, (key, payload, updated_at))
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.execute(sql.SQLITE_SET_STATE, (key, payload, updated_at))

    def upsert_avito_chats(self, chats: list[dict[str, Any]]) -> None:
        self.ensure_schema()
        rows = [_chat_row(chat) for chat in chats if chat.get("id")]
        if not rows:
            return
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for row in rows:
                        cur.execute(sql.POSTGRES_UPSERT_CONVERSATION, row)
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.executemany(sql.SQLITE_UPSERT_CONVERSATION, rows)

    def upsert_avito_messages(self, chat_id: str, messages: list[dict[str, Any]]) -> None:
        self.ensure_schema()
        rows = [_message_row(chat_id, message) for message in messages]
        if not rows:
            return
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for row in rows:
                        cur.execute(sql.POSTGRES_UPSERT_MESSAGE, row)
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.executemany(sql.SQLITE_UPSERT_MESSAGE, rows)

    def list_avito_chats(self, *, limit: int = 20, offset: int = 0, unread_only: bool = False) -> list[dict[str, Any]]:
        self.ensure_schema()
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        rows: list[tuple[str, str]]
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_LIST_CHATS, ("avito", limit, offset))
                    rows = cur.fetchall()
        else:
            assert self.sqlite_path is not None
            with sqlite3.connect(self.sqlite_path) as con:
                rows = con.execute(sql.SQLITE_LIST_CHATS, ("avito", limit, offset)).fetchall()
        chats = [_payload_with_id(payload_json, chat_id) for chat_id, payload_json in rows]
        if unread_only:
            chats = [chat for chat in chats if _chat_has_unread(chat)]
        return chats

    def get_avito_chat(self, chat_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_GET_CHAT, ("avito", chat_id))
                    row = cur.fetchone()
        else:
            assert self.sqlite_path is not None
            with sqlite3.connect(self.sqlite_path) as con:
                row = con.execute(sql.SQLITE_GET_CHAT, ("avito", chat_id)).fetchone()
        return _payload_with_id(row[0], chat_id) if row else None

    def list_avito_messages(self, chat_id: str, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_LIST_MESSAGES, ("avito", chat_id, limit, offset))
                    rows = cur.fetchall()
        else:
            assert self.sqlite_path is not None
            with sqlite3.connect(self.sqlite_path) as con:
                rows = con.execute(sql.SQLITE_LIST_MESSAGES, ("avito", chat_id, limit, offset)).fetchall()
        return [_json_payload(row[0]) for row in rows]

    def record_manager_action(self, chat_id: str, action_type: str, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        row = ("avito", chat_id, action_type, json.dumps(payload, ensure_ascii=False), int(time.time()))
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    cur.execute(sql.POSTGRES_INSERT_MANAGER_ACTION, row)
            return
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.execute(sql.SQLITE_INSERT_MANAGER_ACTION, row)

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

    def export_data(self) -> dict[str, Any]:
        self.ensure_schema()
        export: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "created_at": int(time.time()),
            "source_backend": self.backend,
            "tables": {},
        }
        if self.backend == "postgres":
            with self._postgres_connection() as con:
                with con.cursor() as cur:
                    for table in APPLICATION_TABLES:
                        cur.execute(sql.export_table_query(table))
                        columns = [column.name for column in cur.description]
                        export["tables"][table] = [dict(zip(columns, row)) for row in cur.fetchall()]
            return export
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            con.row_factory = sqlite3.Row
            for table in APPLICATION_TABLES:
                export["tables"][table] = [dict(row) for row in con.execute(sql.export_table_query(table))]
        return export

    def import_data(self, export: dict[str, Any]) -> dict[str, int]:
        self.ensure_schema()
        tables = export.get("tables", {})
        if not isinstance(tables, dict):
            raise ValueError("Runtime storage export must contain a tables object")
        if self.backend == "postgres":
            return self._import_postgres_tables(tables)
        return self._import_sqlite_tables(tables)

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
                for statement in sql.POSTGRES_SCHEMA:
                    cur.execute(statement)
                cur.execute(sql.POSTGRES_SET_SCHEMA_VERSION, (SCHEMA_VERSION,))

    @contextmanager
    def _postgres_connection(self) -> Iterator[Any]:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on deployment env
            raise RuntimeError("PostgreSQL storage requires psycopg. Run dependency install after updating pyproject.") from exc
        assert self.database_url is not None
        with self._postgres_lock:
            if self._postgres_con is None or self._postgres_con.closed:
                self._postgres_con = psycopg.connect(self.database_url, connect_timeout=10)
            try:
                yield self._postgres_con
                self._postgres_con.commit()
            except Exception:
                self._postgres_con.rollback()
                raise

    def _export_json_backup(self, backup_path: Path) -> None:
        export = self.export_data()
        temp_path = backup_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(backup_path)

    def _import_postgres_tables(self, tables: dict[str, Any]) -> dict[str, int]:
        counts = _table_counts(tables)
        with self._postgres_connection() as con:
            with con.cursor() as cur:
                for row in _rows(tables, "app_meta"):
                    cur.execute(sql.POSTGRES_IMPORT_APP_META, (row["key"], row["value"]))
                for row in _rows(tables, "runtime_state"):
                    cur.execute(sql.POSTGRES_IMPORT_STATE, (row["key"], row["value_json"], row["updated_at"]))
                for row in _rows(tables, "conversations"):
                    cur.execute(
                        sql.POSTGRES_IMPORT_CONVERSATION,
                        (
                            row["id"],
                            row["channel"],
                            row["external_chat_id"],
                            row.get("external_item_key"),
                            row.get("title"),
                            row["payload_json"],
                            row["updated_at"],
                        ),
                    )
                for row in _rows(tables, "messages"):
                    cur.execute(
                        sql.POSTGRES_IMPORT_MESSAGE,
                        (
                            row["id"],
                            row["channel"],
                            row["external_chat_id"],
                            row["message_key"],
                            row.get("external_message_id"),
                            row.get("direction"),
                            row.get("message_type"),
                            row.get("author_role"),
                            row.get("created_at"),
                            row.get("text"),
                            row["payload_json"],
                            row["received_at"],
                        ),
                    )
                for row in _rows(tables, "manager_actions"):
                    cur.execute(
                        sql.POSTGRES_IMPORT_MANAGER_ACTION,
                        (
                            row["id"],
                            row["channel"],
                            row["external_chat_id"],
                            row["action_type"],
                            row["payload_json"],
                            row["created_at"],
                        ),
                    )
                _sync_postgres_sequence(cur, "conversations", "id")
                _sync_postgres_sequence(cur, "messages", "id")
                _sync_postgres_sequence(cur, "manager_actions", "id")
        return counts

    def _import_sqlite_tables(self, tables: dict[str, Any]) -> dict[str, int]:
        counts = _table_counts(tables)
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as con:
            for row in _rows(tables, "app_meta"):
                con.execute(sql.SQLITE_IMPORT_APP_META, (row["key"], row["value"]))
            for row in _rows(tables, "runtime_state"):
                con.execute(sql.SQLITE_IMPORT_STATE, (row["key"], row["value_json"], row["updated_at"]))
            for row in _rows(tables, "conversations"):
                con.execute(
                    sql.SQLITE_IMPORT_CONVERSATION,
                    (
                        row["id"],
                        row["channel"],
                        row["external_chat_id"],
                        row.get("external_item_key"),
                        row.get("title"),
                        row["payload_json"],
                        row["updated_at"],
                    ),
                )
            for row in _rows(tables, "messages"):
                con.execute(
                    sql.SQLITE_IMPORT_MESSAGE,
                    (
                        row["id"],
                        row["channel"],
                        row["external_chat_id"],
                        row["message_key"],
                        row.get("external_message_id"),
                        row.get("direction"),
                        row.get("message_type"),
                        row.get("author_role"),
                        row.get("created_at"),
                        row.get("text"),
                        row["payload_json"],
                        row["received_at"],
                    ),
                )
            for row in _rows(tables, "manager_actions"):
                con.execute(
                    sql.SQLITE_IMPORT_MANAGER_ACTION,
                    (
                        row["id"],
                        row["channel"],
                        row["external_chat_id"],
                        row["action_type"],
                        row["payload_json"],
                        row["created_at"],
                    ),
                )
        return counts


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
    item = chat_item_context(chat)
    title = str(chat.get("title") or item.get("title") or "") or None
    item_key = chat_item_key(chat) or None
    return ("avito", chat_id, item_key, title, json.dumps(chat, ensure_ascii=False), int(time.time()))


def _message_row(chat_id: str, message: dict[str, Any]) -> tuple[Any, ...]:
    message_id = message.get("id") or message.get("message_id")
    message_key = str(message_id) if message_id else _stable_message_key(message)
    direction = message.get("direction")
    message_type = message.get("type")
    role = author_role(direction)
    created_at = safe_int(message.get("created") or message.get("created_at"))
    text = message_text(message)
    return (
        "avito",
        chat_id,
        message_key,
        str(message_id) if message_id else None,
        str(direction) if direction else None,
        str(message_type) if message_type else None,
        role,
        created_at,
        text,
        json.dumps(message, ensure_ascii=False),
        int(time.time()),
    )


def _stable_message_key(message: dict[str, Any]) -> str:
    payload = json.dumps(message, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _json_payload(payload_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_with_id(payload_json: str, fallback_id: str) -> dict[str, Any]:
    payload = _json_payload(payload_json)
    payload.setdefault("id", fallback_id)
    return payload


def _chat_has_unread(chat: dict[str, Any]) -> bool:
    if chat.get("unread_count"):
        return True
    last_message = chat.get("last_message")
    if isinstance(last_message, dict):
        if last_message.get("isRead") is False or last_message.get("read") is False:
            return True
        if last_message.get("direction") == "in" and not last_message.get("read"):
            return True
    return False


def _rows(tables: dict[str, Any], table: str) -> list[dict[str, Any]]:
    rows = tables.get(table, [])
    if not isinstance(rows, list):
        raise ValueError(f"Runtime storage export table {table} must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _table_counts(tables: dict[str, Any]) -> dict[str, int]:
    return {table: len(_rows(tables, table)) for table in APPLICATION_TABLES}


def _sync_postgres_sequence(cur: Any, table: str, column: str) -> None:
    cur.execute(sql.postgres_sync_sequence_query(table), (table, column))
