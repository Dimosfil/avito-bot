from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.request import Request, urlopen

from app.runtime_logging import configured_log_dir, log_rotation_settings

try:
    from ai_logger import LogRecord, Logger, build_aggregator_from_env
except ImportError:  # pragma: no cover - exercised in container builds without sibling package
    @dataclass(frozen=True)
    class _LogLevel:
        name: str

    @dataclass(frozen=True)
    class LogRecord:
        level: _LogLevel
        message: str
        context: dict[str, Any]
        timestamp: datetime

    class _JsonlPlugin:
        name = "jsonl"

        def __init__(self, path: str) -> None:
            self.path = Path(path)

        def emit(self, record: LogRecord) -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": record.timestamp.isoformat(),
                "level": record.level.name,
                "message": record.message,
                "context": record.context,
            }
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

        def flush(self) -> None:
            return None

        def close(self) -> None:
            self.flush()

    class _LogAggregator:
        def __init__(self, *, default_context: dict[str, Any] | None = None) -> None:
            self.default_context = default_context or {}
            self.plugins: list[Any] = []
            self.failed_records: deque[tuple[LogRecord, str, str]] = deque(maxlen=100)

        def add_plugin(self, plugin: Any) -> None:
            self.plugins.append(plugin)

        def emit(self, record: LogRecord) -> None:
            for plugin in self.plugins:
                try:
                    plugin.emit(record)
                except Exception as exc:
                    self.failed_records.append((record, getattr(plugin, "name", plugin.__class__.__name__), str(exc)))

    class Logger:
        def __init__(self, name: str, aggregator: _LogAggregator) -> None:
            self.name = name
            self.aggregator = aggregator

        def log(self, level: str, message: str, **context: Any) -> None:
            merged_context = {**self.aggregator.default_context, **context}
            record = LogRecord(
                level=_LogLevel(level.upper()),
                message=message,
                context=merged_context,
                timestamp=datetime.now(UTC),
            )
            self.aggregator.emit(record)

        def info(self, message: str, **context: Any) -> None:
            self.log("INFO", message, **context)

        def warning(self, message: str, **context: Any) -> None:
            self.log("WARNING", message, **context)

        def error(self, message: str, **context: Any) -> None:
            self.log("ERROR", message, **context)

    def build_aggregator_from_env(
        environ: Mapping[str, str] | None = None,
        default_context: dict[str, Any] | None = None,
    ) -> _LogAggregator:
        env = environ if environ is not None else os.environ
        aggregator = _LogAggregator(default_context=default_context)
        jsonl_path = env.get("AI_LOGGER_JSONL_PATH")
        if jsonl_path:
            aggregator.add_plugin(_JsonlPlugin(jsonl_path))
        return aggregator


class _HttpPlugin:
    name = "http"

    def __init__(self, url: str, token: str | None = None, logger_name: str | None = None) -> None:
        self.url = url
        self.token = token
        self.logger_name = logger_name

    def emit(self, record: LogRecord) -> None:
        payload = json.dumps(
            {
                "timestamp": record.timestamp.isoformat(),
                "level": record.level.name,
                "message": record.message,
                "context": record.context,
                "logger": self.logger_name,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.url, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=3):
            pass

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.flush()


class _RotatingJsonlPlugin:
    name = "jsonl"

    def __init__(self, path: Path, *, max_bytes: int, backup_count: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def emit(self, record: LogRecord) -> None:
        payload = json.dumps(
            {
                "timestamp": record.timestamp.isoformat(),
                "level": record.level.name,
                "message": record.message,
                "context": record.context,
            },
            ensure_ascii=False,
        ) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed(len(payload.encode("utf-8")))
        with self.path.open("a", encoding="utf-8") as file:
            file.write(payload)

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.exists() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self.backup_count - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            if source.exists():
                source.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
        self.path.replace(self.path.with_name(f"{self.path.name}.1"))

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.flush()


SECRET_KEY_PARTS = ("token", "secret", "password", "key", "authorization", "cookie")


class AdminLogBuffer:
    name = "admin_memory"

    def __init__(self, *, maxlen: int = 300) -> None:
        self._sequence = 0
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)

    @property
    def maxlen(self) -> int:
        return int(self._records.maxlen or 0)

    def record(self, level: str, event: str, detail: Any | None = None) -> None:
        self._sequence += 1
        self._records.append(
            {
                "id": self._sequence,
                "created_at": None,
                "level": level,
                "event": event,
                "detail": safe_log_detail(detail),
            }
        )

    def emit(self, record: LogRecord) -> None:
        self._sequence += 1
        detail = record.context.get("detail", record.context)
        self._records.append(
            {
                "id": self._sequence,
                "created_at": record.timestamp.timestamp(),
                "level": record.level.name.lower(),
                "event": record.message,
                "detail": safe_log_detail(detail),
            }
        )

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.flush()

    def list(self, *, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(limit, self.maxlen or 300))
        records = list(self._records)[-limit:]
        return {"logs": records, "count": len(records), "max_count": self.maxlen}

    def clear(self) -> None:
        self._sequence = 0
        self._records.clear()


def create_runtime_logger(
    name: str,
    *,
    admin_buffer: AdminLogBuffer,
    environ: Mapping[str, str] | None = None,
    context: dict[str, Any] | None = None,
) -> Logger:
    effective_environ = environ if environ is not None else os.environ
    # Keep HTTP delivery stable whether the optional ai_logger package is
    # installed or the Docker fallback is active.
    plugin_environ = dict(effective_environ)
    server_url = plugin_environ.pop("AI_LOGGER_SERVER_URL", None)
    server_token = plugin_environ.pop("AI_LOGGER_SERVER_TOKEN", None)
    jsonl_path = plugin_environ.pop("AI_LOGGER_JSONL_PATH", None)
    aggregator = build_aggregator_from_env(plugin_environ, default_context=context)
    log_dir = configured_log_dir(effective_environ)
    if jsonl_path:
        events_path = Path(jsonl_path)
        if not events_path.is_absolute():
            raise ValueError("AI_LOGGER_JSONL_PATH must be an absolute path")
    elif log_dir is not None:
        events_path = log_dir / "events.jsonl"
    else:
        events_path = None
    if events_path is not None:
        max_bytes, backup_count = log_rotation_settings(effective_environ)
        aggregator.add_plugin(_RotatingJsonlPlugin(events_path, max_bytes=max_bytes, backup_count=backup_count))
    if server_url:
        aggregator.add_plugin(_HttpPlugin(server_url, server_token, logger_name=name))
    aggregator.add_plugin(admin_buffer)
    return Logger(name, aggregator)


def safe_log_detail(detail: Any | None) -> Any:
    if detail is None:
        return None
    if isinstance(detail, dict):
        sanitized: dict[str, Any] = {}
        for key, value in detail.items():
            key_text = str(key)
            if any(secret_word in key_text.lower() for secret_word in SECRET_KEY_PARTS):
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = safe_log_detail(value)
        return sanitized
    if isinstance(detail, list):
        return [safe_log_detail(item) for item in detail[:20]]
    if isinstance(detail, (str, int, float, bool)):
        return detail
    return str(detail)
