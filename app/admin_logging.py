from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from ai_logger import LogRecord, Logger, build_aggregator_from_env


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
