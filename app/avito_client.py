from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
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


@dataclass(frozen=True)
class _CachedToken:
    token: AvitoToken
    valid_until: float


class AvitoClient:
    _token_cache: dict[tuple[str, str, str], _CachedToken] = {}
    _token_locks: dict[tuple[str, str, str], asyncio.Lock] = {}
    _user_id_cache: dict[tuple[str, str, str], str] = {}
    _user_id_locks: dict[tuple[str, str, str], asyncio.Lock] = {}

    def __init__(self, settings: Settings, timeout: float = 20.0) -> None:
        self._settings = settings
        self._timeout = timeout

    async def get_access_token(self) -> AvitoToken:
        if not self._settings.avito_client_id or not self._settings.avito_client_secret:
            raise AvitoConfigError("AVITO_CLIENT_ID and AVITO_CLIENT_SECRET are required")

        cache_key = self._cache_key()
        cached = self._valid_cached_token(cache_key)
        if cached is not None:
            return cached

        lock = self._token_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._valid_cached_token(cache_key)
            if cached is not None:
                return cached
            token = await self._fetch_access_token()
            if token.expires_in is not None and token.expires_in > 0:
                lifetime = float(token.expires_in)
                refresh_skew = min(60.0, max(1.0, lifetime * 0.1))
                self._token_cache[cache_key] = _CachedToken(
                    token=token,
                    valid_until=time.monotonic() + max(1.0, lifetime - refresh_skew),
                )
            return token

    async def _fetch_access_token(self) -> AvitoToken:
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

    async def get_item_stats(
        self,
        item_ids: list[int],
        date_from: str,
        date_to: str,
        period_grouping: str = "day",
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        user_id = await self._resolve_user_id()
        body: dict[str, Any] = {
            "itemIds": item_ids,
            "dateFrom": date_from,
            "dateTo": date_to,
            "periodGrouping": period_grouping,
        }
        if fields:
            body["fields"] = fields
        return await self._request("POST", f"/stats/v1/accounts/{user_id}/items", json=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        token = await self.get_access_token()
        response = await self._send_request(method, path, token, params=params, json=json)
        if response.status_code == 401:
            self._invalidate_token(token.access_token)
            token = await self.get_access_token()
            response = await self._send_request(method, path, token, params=params, json=json)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    async def _send_request(
        self,
        method: str,
        path: str,
        token: AvitoToken,
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.request(
                method,
                f"{self._settings.avito_base_url}{path}",
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {token.access_token}"},
            )

    async def _resolve_user_id(self) -> str:
        if self._settings.avito_user_id:
            return self._settings.avito_user_id

        cache_key = self._cache_key()
        cached = self._user_id_cache.get(cache_key)
        if cached is not None:
            return cached

        lock = self._user_id_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._user_id_cache.get(cache_key)
            if cached is not None:
                return cached
            account = await self.get_account_self()
            user_id = account.get("id") or account.get("user_id") or account.get("account_id")
            if user_id is None:
                raise AvitoConfigError("Could not infer Avito user id from /core/v1/accounts/self")
            resolved = str(user_id)
            self._user_id_cache[cache_key] = resolved
            return resolved

    def _cache_key(self) -> tuple[str, str, str]:
        return (
            self._settings.avito_base_url,
            self._settings.avito_client_id or "",
            self._settings.avito_client_secret or "",
        )

    def _valid_cached_token(self, cache_key: tuple[str, str, str]) -> AvitoToken | None:
        cached = self._token_cache.get(cache_key)
        if cached is None:
            return None
        if time.monotonic() >= cached.valid_until:
            self._token_cache.pop(cache_key, None)
            return None
        return cached.token

    def _invalidate_token(self, access_token: str) -> None:
        cache_key = self._cache_key()
        cached = self._token_cache.get(cache_key)
        if cached is not None and cached.token.access_token == access_token:
            self._token_cache.pop(cache_key, None)

    @classmethod
    def clear_runtime_cache(cls) -> None:
        cls._token_cache.clear()
        cls._token_locks.clear()
        cls._user_id_cache.clear()
        cls._user_id_locks.clear()
