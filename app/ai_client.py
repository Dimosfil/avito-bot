from __future__ import annotations

from app.codex_app_server_client import CodexAppServerClient
from app.deepseek_client import ChatMessage, DeepSeekClient


class FallbackAIClient:
    def __init__(self, primary: DeepSeekClient, fallback: CodexAppServerClient | None) -> None:
        self._primary = primary
        self._fallback = fallback

    async def create_chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        try:
            return await self._primary.create_chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            if self._fallback is None:
                raise
            return await self._fallback.create_chat_completion(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    async def ping(self) -> str:
        try:
            return await self._primary.ping()
        except Exception:
            if self._fallback is None:
                raise
            return await self._fallback.ping()
