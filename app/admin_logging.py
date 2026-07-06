from __future__ import annotations

import time
from collections import deque
from typing import Any


SECRET_KEY_PARTS = ("token", "secret", "password", "key")


class AdminLogBuffer:
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
                "created_at": time.time(),
                "level": level,
                "event": event,
                "detail": safe_log_detail(detail),
            }
        )

    def list(self, *, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(limit, self.maxlen or 300))
        records = list(self._records)[-limit:]
        return {"logs": records, "count": len(records), "max_count": self.maxlen}

    def clear(self) -> None:
        self._sequence = 0
        self._records.clear()


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
