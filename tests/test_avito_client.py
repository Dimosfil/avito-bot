import httpx
import pytest

import app.avito_client as avito_client_module
from app.avito_client import AvitoClient
from app.config import Settings


@pytest.fixture(autouse=True)
def clear_avito_runtime_cache() -> None:
    AvitoClient.clear_runtime_cache()


def _settings() -> Settings:
    return Settings(
        avito_client_id="client-id",
        avito_client_secret="client-secret",
        avito_user_id=None,
        avito_webhook_url=None,
        ai_provider="deepseek",
        deepseek_api_key=None,
        deepseek_model="model",
        codex_app_server_base_url=None,
        codex_app_server_api_key=None,
        codex_app_server_model="codex",
        avito_base_url="https://avito.test",
    )


def _install_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return async_client(transport=transport, **kwargs)

    monkeypatch.setattr(avito_client_module.httpx, "AsyncClient", client_factory)


@pytest.mark.anyio
async def test_reuses_token_and_resolved_user_across_client_instances(monkeypatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
        if request.url.path == "/core/v1/accounts/self":
            return httpx.Response(200, json={"id": 123})
        if request.url.path.endswith("/chats"):
            return httpx.Response(200, json={"chats": []})
        if request.url.path.endswith("/messages/"):
            return httpx.Response(200, json={"messages": []})
        raise AssertionError(f"Unexpected request: {request.url}")

    _install_transport(monkeypatch, handler)

    await AvitoClient(_settings()).get_chats()
    await AvitoClient(_settings()).get_messages("chat-1")

    assert calls.count("/token") == 1
    assert calls.count("/core/v1/accounts/self") == 1


@pytest.mark.anyio
async def test_refreshes_cached_token_once_after_unauthorized_response(monkeypatch) -> None:
    issued_tokens: list[str] = []
    chat_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chat_attempts
        if request.url.path == "/token":
            token = f"token-{len(issued_tokens) + 1}"
            issued_tokens.append(token)
            return httpx.Response(200, json={"access_token": token, "expires_in": 3600})
        if request.url.path == "/core/v1/accounts/self":
            return httpx.Response(200, json={"id": 123})
        if request.url.path.endswith("/chats"):
            chat_attempts += 1
            if chat_attempts == 1:
                return httpx.Response(401, json={"error": "expired"})
            return httpx.Response(200, json={"chats": []})
        raise AssertionError(f"Unexpected request: {request.url}")

    _install_transport(monkeypatch, handler)

    response = await AvitoClient(_settings()).get_chats()

    assert response == {"chats": []}
    assert issued_tokens == ["token-1", "token-2"]
    assert chat_attempts == 2
