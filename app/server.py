from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from app.runtime_logging import ensure_log_dir, log_rotation_settings, uvicorn_log_config


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    host = os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _listener_port()
    log_dir = ensure_log_dir(fallback=ROOT / ".codex-runtime" / "logs")
    max_bytes, backup_count = log_rotation_settings()
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_config=uvicorn_log_config(log_dir, max_bytes=max_bytes, backup_count=backup_count),
    )


def _listener_port() -> int:
    value = (os.getenv("PORT") or os.getenv("API_PORT") or "8000").strip()
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError("PORT or API_PORT must be a numeric TCP port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT or API_PORT must be between 1 and 65535")
    return port


if __name__ == "__main__":
    main()
