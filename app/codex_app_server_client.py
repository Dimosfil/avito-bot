from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.deepseek_client import ChatMessage


class CodexAppServerConfigError(RuntimeError):
    pass


class CodexAppServerClient:
    def __init__(self, settings: Settings, timeout: float = 45.0) -> None:
        self._settings = settings
        self._timeout = timeout

    async def create_chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        if not self._settings.codex_app_server_base_url:
            raise CodexAppServerConfigError("CODEX_APP_SERVER_BASE_URL is required")

        payload: dict[str, Any] = {
            "model": self._settings.codex_app_server_model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self._settings.codex_app_server_api_key:
            headers["Authorization"] = f"Bearer {self._settings.codex_app_server_api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._settings.codex_app_server_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"].get("content")
        return (content or "").strip()

    async def ping(self) -> str:
        return await self.create_chat_completion(
            [
                ChatMessage(role="system", content="Reply with exactly: ok"),
                ChatMessage(role="user", content="Health check"),
            ],
            temperature=0,
            max_tokens=10,
        )
