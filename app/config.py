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
    deepseek_api_key: str | None
    deepseek_model: str
    avito_base_url: str = "https://api.avito.ru"
    deepseek_base_url: str = "https://api.deepseek.com"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            avito_client_id=_blank_to_none(os.getenv("AVITO_CLIENT_ID")),
            avito_client_secret=_blank_to_none(os.getenv("AVITO_CLIENT_SECRET")),
            avito_user_id=_blank_to_none(os.getenv("AVITO_USER_ID")),
            avito_webhook_url=_blank_to_none(os.getenv("AVITO_WEBHOOK_URL")),
            deepseek_api_key=_blank_to_none(os.getenv("DEEPSEEK_API_KEY")),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
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
            "avito_client_id_preview": mask_value(self.avito_client_id),
            "deepseek_api_key_configured": bool(self.deepseek_api_key),
            "deepseek_model": self.deepseek_model,
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
