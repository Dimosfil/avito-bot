from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


class AvitoConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AvitoToken:
    access_token: str
    token_type: str | None = None
    expires_in: int | None = None
    raw: dict[str, Any] | None = None


class AvitoClient:
    def __init__(self, settings: Settings, timeout: float = 20.0) -> None:
        self._settings = settings
        self._timeout = timeout

    async def get_access_token(self) -> AvitoToken:
        if not self._settings.avito_client_id or not self._settings.avito_client_secret:
            raise AvitoConfigError("AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._settings.avito_base_url}/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.avito_client_id,
                    "client_secret": self._settings.avito_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        response.raise_for_status()
        payload = response.json()
        return AvitoToken(
            access_token=payload["access_token"],
            token_type=payload.get("token_type"),
            expires_in=payload.get("expires_in"),
            raw=payload,
        )

    async def get_account_self(self) -> dict[str, Any]:
        return await self._request("GET", "/core/v1/accounts/self")

    async def get_chats(self, limit: int = 20, offset: int = 0, unread_only: bool = False) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        return await self._request(
            "GET",
            f"/messenger/v2/accounts/{user_id}/chats",
            params={
                "limit": limit,
                "offset": offset,
                "unread_only": str(unread_only).lower(),
            },
        )

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        return await self._request("GET", f"/messenger/v2/accounts/{user_id}/chats/{chat_id}")

    async def get_messages(self, chat_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        return await self._request(
            "GET",
            f"/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/",
            params={"limit": limit, "offset": offset},
        )

    async def send_text_message(self, chat_id: str, text: str) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        return await self._request(
            "POST",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages",
            json={"type": "text", "message": {"text": text}},
        )

    async def mark_chat_read(self, chat_id: str) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        return await self._request("POST", f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/read")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method,
                f"{self._settings.avito_base_url}{path}",
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    async def _resolve_user_id(self) -> str:
        if self._settings.avito_user_id:
            return self._settings.avito_user_id

        account = await self.get_account_self()
        user_id = account.get("id") or account.get("user_id") or account.get("account_id")
        if user_id is None:
            raise AvitoConfigError("Could not infer Avito user id from /core/v1/accounts/self")
        return str(user_id)
