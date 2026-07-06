from __future__ import annotations

from app.ai_client import FallbackAIClient
from app.codex_app_server_client import CodexAppServerClient
from app.config import Settings
from app.deepseek_client import DeepSeekClient, DeepSeekConfigError


def create_ai_client(
    settings: Settings,
    *,
    deepseek_client_cls=DeepSeekClient,
    codex_client_cls=CodexAppServerClient,
) -> DeepSeekClient | CodexAppServerClient | FallbackAIClient:
    provider = settings.ai_provider.strip().lower()
    if provider == "deepseek":
        fallback = codex_client_cls(settings) if settings.codex_app_server_base_url else None
        return FallbackAIClient(deepseek_client_cls(settings), fallback)
    if provider == "codex_app_server":
        return codex_client_cls(settings)
    raise DeepSeekConfigError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
