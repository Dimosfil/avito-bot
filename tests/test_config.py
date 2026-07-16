from app.ai_client import FallbackAIClient
from app.config import Settings, get_settings, mask_value
from app.codex_app_server_client import CodexAppServerClient
from app.main import create_ai_client


def test_mask_value_hides_middle() -> None:
    assert mask_value("abcdefghijkl") == "abcd...ijkl"


def test_public_status_does_not_expose_secret() -> None:
    settings = Settings(
        avito_client_id="client-id-123",
        avito_client_secret="secret-value",
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="deepseek",
        deepseek_api_key="deepseek-secret",
        deepseek_model="deepseek-v4-flash",
        codex_app_server_base_url=None,
        codex_app_server_api_key=None,
        codex_app_server_model="codex",
    )

    status = settings.public_status()

    assert status["avito_client_secret_configured"] is True
    assert "secret-value" not in str(status)
    assert status["deepseek_api_key_configured"] is True
    assert "deepseek-secret" not in str(status)
    assert status["ai_provider"] == "deepseek"
    assert status["codex_app_server_configured"] is False


def test_avito_live_sync_flag_can_disable_live_api(monkeypatch) -> None:
    monkeypatch.setenv("AVITO_LIVE_SYNC_ENABLED", "false")

    status = get_settings().public_status()

    assert status["avito_live_sync_enabled"] is False


def test_autoreply_interval_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv("AVITO_AUTOREPLY_INTERVAL_SECONDS", "45")

    status = get_settings().public_status()

    assert status["autoreply_interval_seconds"] == 45


def test_ai_logger_can_be_configured_from_env(monkeypatch) -> None:
    monkeypatch.setenv("AI_LOGGER_LEVEL", "DEBUG")
    monkeypatch.setenv("AI_LOGGER_PROJECT", "avito-bot")
    monkeypatch.setenv("AI_LOGGER_SERVICE", "api")
    monkeypatch.setenv("AI_LOGGER_ENVIRONMENT", "dev")
    monkeypatch.setenv("AI_LOGGER_SERVER_URL", "http://127.0.0.1:8765/ingest")
    monkeypatch.setenv("AI_LOGGER_SERVER_TOKEN", "secret-token")
    monkeypatch.setenv("AI_LOGGER_JSONL_PATH", ".codex-runtime/logs/runtime.jsonl")

    settings = get_settings()

    assert settings.ai_logger_level == "DEBUG"
    assert settings.ai_logger_project == "avito-bot"
    assert settings.ai_logger_service == "api"
    assert settings.ai_logger_environment == "dev"
    assert settings.ai_logger_server_url == "http://127.0.0.1:8765/ingest"
    assert settings.ai_logger_jsonl_path == ".codex-runtime/logs/runtime.jsonl"
    assert settings.public_status()["ai_logger_server_configured"] is True
    assert settings.public_status()["ai_logger_server_token_configured"] is True
    assert "secret-token" not in str(settings.public_status())


def test_create_ai_client_defaults_to_deepseek() -> None:
    settings = Settings(
        avito_client_id=None,
        avito_client_secret=None,
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="deepseek",
        deepseek_api_key="deepseek-secret",
        deepseek_model="deepseek-v4-flash",
        codex_app_server_base_url=None,
        codex_app_server_api_key=None,
        codex_app_server_model="codex",
    )

    assert isinstance(create_ai_client(settings), FallbackAIClient)


def test_create_ai_client_uses_codex_app_server_as_deepseek_fallback() -> None:
    settings = Settings(
        avito_client_id=None,
        avito_client_secret=None,
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="deepseek",
        deepseek_api_key="deepseek-secret",
        deepseek_model="deepseek-v4-flash",
        codex_app_server_base_url="http://127.0.0.1:9876/v1",
        codex_app_server_api_key=None,
        codex_app_server_model="codex-local",
    )

    assert isinstance(create_ai_client(settings), FallbackAIClient)


def test_create_ai_client_supports_codex_app_server() -> None:
    settings = Settings(
        avito_client_id=None,
        avito_client_secret=None,
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="codex_app_server",
        deepseek_api_key=None,
        deepseek_model="deepseek-v4-flash",
        codex_app_server_base_url="http://127.0.0.1:9876/v1",
        codex_app_server_api_key=None,
        codex_app_server_model="codex-local",
    )

    assert isinstance(create_ai_client(settings), CodexAppServerClient)
