import json
import logging.config

import pytest

from app.admin_logging import AdminLogBuffer, create_runtime_logger
from app.runtime_logging import configured_log_dir, ensure_log_dir, log_rotation_settings, uvicorn_log_config


def test_log_dir_defaults_below_shared_runtime_storage(tmp_path) -> None:
    log_dir = configured_log_dir({"SHARED_DIR": str(tmp_path)})

    assert log_dir == tmp_path / "avito-bot" / "logs"


def test_log_dir_requires_absolute_configured_path() -> None:
    with pytest.raises(ValueError, match="AVITO_LOG_DIR must be an absolute path"):
        configured_log_dir({"AVITO_LOG_DIR": "relative/logs"})


def test_ensure_log_dir_creates_fallback(tmp_path) -> None:
    log_dir = ensure_log_dir({}, fallback=tmp_path / "runtime-logs")

    assert log_dir.is_dir()


def test_uvicorn_log_config_writes_runtime_file(tmp_path) -> None:
    config = uvicorn_log_config(tmp_path, max_bytes=1024, backup_count=2)
    logging.config.dictConfig(config)

    logging.getLogger("uvicorn.error").info("startup-visible")

    assert "startup-visible" in (tmp_path / "runtime.log").read_text(encoding="utf-8")


def test_event_log_defaults_to_configured_folder_and_rotates(tmp_path) -> None:
    logger = create_runtime_logger(
        "tests.runtime",
        admin_buffer=AdminLogBuffer(maxlen=10),
        environ={
            "AVITO_LOG_DIR": str(tmp_path),
            "AVITO_LOG_MAX_BYTES": "180",
            "AVITO_LOG_BACKUP_COUNT": "2",
        },
    )

    for index in range(5):
        logger.info("event", detail={"index": index, "value": "x" * 50})

    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "events.jsonl.1").exists()
    records = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[-1]["message"] == "event"


def test_log_rotation_settings_reject_invalid_values_with_defaults() -> None:
    assert log_rotation_settings({"AVITO_LOG_MAX_BYTES": "bad", "AVITO_LOG_BACKUP_COUNT": "0"}) == (
        5 * 1024 * 1024,
        5,
    )
