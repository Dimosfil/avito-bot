from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5


def configured_log_dir(environ: Mapping[str, str] | None = None) -> Path | None:
    env = os.environ if environ is None else environ
    explicit = _non_blank(env.get("AVITO_LOG_DIR"))
    if explicit:
        return _absolute_path(explicit, "AVITO_LOG_DIR")

    shared_dir = _non_blank(env.get("SHARED_DIR"))
    if shared_dir:
        return _absolute_path(shared_dir, "SHARED_DIR") / "avito-bot" / "logs"
    return None


def ensure_log_dir(environ: Mapping[str, str] | None = None, *, fallback: Path | None = None) -> Path:
    log_dir = configured_log_dir(environ)
    if log_dir is None:
        if fallback is None:
            raise RuntimeError("AVITO_LOG_DIR or SHARED_DIR is required for persistent runtime logs")
        log_dir = fallback.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_rotation_settings(environ: Mapping[str, str] | None = None) -> tuple[int, int]:
    env = os.environ if environ is None else environ
    return (
        _positive_int(env.get("AVITO_LOG_MAX_BYTES"), DEFAULT_LOG_MAX_BYTES),
        _positive_int(env.get("AVITO_LOG_BACKUP_COUNT"), DEFAULT_LOG_BACKUP_COUNT),
    )


def uvicorn_log_config(log_dir: Path, *, max_bytes: int, backup_count: int) -> dict[str, object]:
    runtime_path = log_dir / "runtime.log"
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(runtime_path),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8",
        },
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "access",
            "stream": "ext://sys.stdout",
        },
    }
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s %(levelname)s %(client_addr)s "%(request_line)s" %(status_code)s',
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "use_colors": False,
            },
        },
        "handlers": handlers,
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "uvicorn.access": {
                "handlers": ["access_console", "file"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {"handlers": ["console", "file"], "level": "INFO"},
    }


def _absolute_path(value: str, name: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return path


def _non_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _positive_int(value: str | None, default: int) -> int:
    if not value or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
