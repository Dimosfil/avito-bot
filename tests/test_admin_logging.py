from app.admin_logging import AdminLogBuffer, safe_log_detail


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
