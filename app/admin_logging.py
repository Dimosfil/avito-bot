from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping

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
            self.failed_records: list[tuple[LogRecord, str, str]] = []

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
        env = environ or {}
        aggregator = _LogAggregator(default_context=default_context)
        jsonl_path = env.get("AI_LOGGER_JSONL_PATH")
        if jsonl_path:
            aggregator.add_plugin(_JsonlPlugin(jsonl_path))
        return aggregator


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
    aggregator = build_aggregator_from_env(environ, default_context=context)
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
