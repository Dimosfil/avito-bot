from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


class DeepSeekConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class DeepSeekClient:
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
        if not self._settings.deepseek_api_key:
            raise DeepSeekConfigError("DEEPSEEK_API_KEY is required")

        payload: dict[str, Any] = {
            "model": self._settings.deepseek_model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "thinking": {"type": "disabled"},
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._settings.deepseek_base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
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
