import json

import app.admin_logging as admin_logging
from app.admin_logging import AdminLogBuffer, create_runtime_logger, safe_log_detail


def test_admin_log_buffer_records_recent_limited_events() -> None:
    logs = AdminLogBuffer(maxlen=2)

    logs.record("info", "first")
    logs.record("warning", "second")
    logs.record("error", "third")

    data = logs.list(limit=10)

    assert data["count"] == 2
    assert data["max_count"] == 2
    assert [entry["event"] for entry in data["logs"]] == ["second", "third"]
    assert [entry["id"] for entry in data["logs"]] == [2, 3]


def test_safe_log_detail_redacts_secret_values_and_limits_lists() -> None:
    detail = safe_log_detail(
        {
            "token": "secret-token",
            "nested": {"api_key": "secret-key", "ok": "visible"},
            "items": list(range(25)),
        }
    )

    assert detail["token"] == "<redacted>"
    assert detail["nested"] == {"api_key": "<redacted>", "ok": "visible"}
    assert detail["items"] == list(range(20))


def test_runtime_logger_sends_sanitized_events_to_admin_and_ai_logger_jsonl(tmp_path) -> None:
    buffer = AdminLogBuffer(maxlen=10)
    path = tmp_path / "runtime.jsonl"
    logger = create_runtime_logger(
        "tests.runtime",
        admin_buffer=buffer,
        environ={"AI_LOGGER_JSONL_PATH": str(path), "AI_LOGGER_LEVEL": "DEBUG"},
        context={"project": "avito-bot", "service": "tests"},
    )

    logger.info("event", detail=safe_log_detail({"api_key": "secret", "ok": "visible"}))

    memory_record = buffer.list()["logs"][0]
    file_record = json.loads(path.read_text(encoding="utf-8").strip())
    assert memory_record["detail"] == {"api_key": "<redacted>", "ok": "visible"}
    assert file_record["context"]["detail"] == memory_record["detail"]
    assert file_record["message"] == "event"
    assert file_record["context"]["project"] == "avito-bot"


def test_runtime_logger_keeps_admin_log_when_external_plugin_fails() -> None:
    class BrokenPlugin:
        name = "broken"

        def emit(self, record):
            raise RuntimeError("boom")

        def flush(self):
            return None

        def close(self):
            return None

    buffer = AdminLogBuffer(maxlen=10)
    logger = create_runtime_logger("tests.runtime", admin_buffer=buffer)
    logger.aggregator.add_plugin(BrokenPlugin())

    logger.warning("still-recorded")

    assert buffer.list()["logs"][0]["event"] == "still-recorded"
    assert logger.aggregator.failed_records[0][1] == "broken"


def test_runtime_logger_sends_sanitized_events_to_ai_logger_ingest(monkeypatch) -> None:
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(admin_logging, "urlopen", fake_urlopen)
    buffer = AdminLogBuffer(maxlen=10)
    logger = create_runtime_logger(
        "tests.runtime",
        admin_buffer=buffer,
        environ={
            "AI_LOGGER_SERVER_URL": "http://logger.test/ingest",
            "AI_LOGGER_SERVER_TOKEN": "test-token",
        },
        context={"project": "avito-bot"},
    )

    logger.info("event", detail=safe_log_detail({"api_key": "secret", "ok": "visible"}))

    request, timeout = requests[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert timeout == 3
    assert request.full_url == "http://logger.test/ingest"
    assert request.get_header("Authorization") == "Bearer test-token"
    assert payload["logger"] == "tests.runtime"
    assert payload["context"]["detail"] == {"api_key": "<redacted>", "ok": "visible"}
    assert payload["message"] == "event"
