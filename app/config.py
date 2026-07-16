from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    avito_client_id: str | None
    avito_client_secret: str | None
    avito_user_id: str | None
    avito_webhook_url: str | None
    ai_provider: str
    deepseek_api_key: str | None
    deepseek_model: str
    codex_app_server_base_url: str | None
    codex_app_server_api_key: str | None
    codex_app_server_model: str
    database_url: str | None = None
    avito_database_path: str | None = None
    avito_backup_dir: str | None = None
    shared_dir: str | None = None
    autoreply_interval_seconds: int = 30
    backup_interval_seconds: int = 21600
    backup_retention_count: int = 14
    telegram_bot_token: str | None = None
    manager_telegram_chat_id: str | None = None
    telegram_notify_timeout_seconds: int = 5
    avito_live_sync_enabled: bool = True
    avito_base_url: str = "https://api.avito.ru"
    deepseek_base_url: str = "https://api.deepseek.com"
    ai_logger_level: str = "INFO"
    ai_logger_project: str | None = None
    ai_logger_service: str | None = None
    ai_logger_environment: str | None = None
    ai_logger_server_url: str | None = None
    ai_logger_server_token: str | None = None
    ai_logger_jsonl_path: str | None = None
    ai_logger_fallback_jsonl_path: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            avito_client_id=_blank_to_none(os.getenv("AVITO_CLIENT_ID")),
            avito_client_secret=_blank_to_none(os.getenv("AVITO_CLIENT_SECRET")),
            avito_user_id=_blank_to_none(os.getenv("AVITO_USER_ID")),
            avito_webhook_url=_blank_to_none(os.getenv("AVITO_WEBHOOK_URL")),
            avito_live_sync_enabled=_bool_from_env(os.getenv("AVITO_LIVE_SYNC_ENABLED"), True),
            ai_provider=(os.getenv("AI_PROVIDER", "deepseek").strip() or "deepseek"),
            deepseek_api_key=_blank_to_none(os.getenv("DEEPSEEK_API_KEY")),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
            codex_app_server_base_url=_blank_to_none(os.getenv("CODEX_APP_SERVER_BASE_URL")),
            codex_app_server_api_key=_blank_to_none(os.getenv("CODEX_APP_SERVER_API_KEY")),
            codex_app_server_model=os.getenv("CODEX_APP_SERVER_MODEL", "codex").strip() or "codex",
            database_url=_blank_to_none(os.getenv("DATABASE_URL")),
            avito_database_path=_blank_to_none(os.getenv("AVITO_DATABASE_PATH")),
            avito_backup_dir=_blank_to_none(os.getenv("AVITO_BACKUP_DIR")),
            shared_dir=_blank_to_none(os.getenv("SHARED_DIR")),
            autoreply_interval_seconds=_positive_int(os.getenv("AVITO_AUTOREPLY_INTERVAL_SECONDS"), 30),
            backup_interval_seconds=_positive_int(os.getenv("AVITO_BACKUP_INTERVAL_SECONDS"), 21600),
            backup_retention_count=_positive_int(os.getenv("AVITO_BACKUP_RETENTION_COUNT"), 14),
            telegram_bot_token=_blank_to_none(os.getenv("TELEGRAM_BOT_TOKEN")),
            manager_telegram_chat_id=_blank_to_none(os.getenv("MANAGER_TELEGRAM_CHAT_ID")),
            telegram_notify_timeout_seconds=_positive_int(os.getenv("TELEGRAM_NOTIFY_TIMEOUT_SECONDS"), 5),
            ai_logger_level=os.getenv("AI_LOGGER_LEVEL", "INFO").strip() or "INFO",
            ai_logger_project=_blank_to_none(os.getenv("AI_LOGGER_PROJECT")),
            ai_logger_service=_blank_to_none(os.getenv("AI_LOGGER_SERVICE")),
            ai_logger_environment=_blank_to_none(os.getenv("AI_LOGGER_ENVIRONMENT")),
            ai_logger_server_url=_blank_to_none(os.getenv("AI_LOGGER_SERVER_URL")),
            ai_logger_server_token=_blank_to_none(os.getenv("AI_LOGGER_SERVER_TOKEN")),
            ai_logger_jsonl_path=_blank_to_none(os.getenv("AI_LOGGER_JSONL_PATH")),
            ai_logger_fallback_jsonl_path=_blank_to_none(os.getenv("AI_LOGGER_FALLBACK_JSONL_PATH")),
        )

    @property
    def has_avito_credentials(self) -> bool:
        return bool(self.avito_client_id and self.avito_client_secret)

    def public_status(self) -> dict[str, object]:
        return {
            "avito_client_id_configured": bool(self.avito_client_id),
            "avito_client_secret_configured": bool(self.avito_client_secret),
            "avito_user_id_configured": bool(self.avito_user_id),
            "avito_webhook_url_configured": bool(self.avito_webhook_url),
            "avito_live_sync_enabled": self.avito_live_sync_enabled,
            "avito_client_id_preview": mask_value(self.avito_client_id),
            "ai_provider": self.ai_provider,
            "deepseek_api_key_configured": bool(self.deepseek_api_key),
            "deepseek_model": self.deepseek_model,
            "codex_app_server_configured": bool(self.codex_app_server_base_url),
            "codex_app_server_model": self.codex_app_server_model,
            "database_url_configured": bool(self.database_url),
            "shared_dir_configured": bool(self.shared_dir),
            "autoreply_interval_seconds": self.autoreply_interval_seconds,
            "backup_dir_configured": bool(self.avito_backup_dir),
            "backup_interval_seconds": self.backup_interval_seconds,
            "backup_retention_count": self.backup_retention_count,
            "telegram_bot_configured": bool(self.telegram_bot_token),
            "manager_telegram_chat_configured": bool(self.manager_telegram_chat_id),
            "telegram_notify_timeout_seconds": self.telegram_notify_timeout_seconds,
            "ai_logger_level": self.ai_logger_level,
            "ai_logger_project": self.ai_logger_project,
            "ai_logger_service": self.ai_logger_service,
            "ai_logger_environment": self.ai_logger_environment,
            "ai_logger_server_configured": bool(self.ai_logger_server_url),
            "ai_logger_server_token_configured": bool(self.ai_logger_server_token),
            "ai_logger_jsonl_configured": bool(self.ai_logger_jsonl_path),
            "ai_logger_fallback_jsonl_configured": bool(self.ai_logger_fallback_jsonl_path),
        }


def get_settings() -> Settings:
    return Settings.from_env()


def mask_value(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _positive_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
