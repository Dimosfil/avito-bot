import asyncio

from app.ai_client import FallbackAIClient


class FailingClient:
    async def create_chat_completion(self, messages, *, temperature=0.3, max_tokens=500):
        raise RuntimeError("primary failed")


class RecordingClient:
    def __init__(self) -> None:
        self.called = False

    async def create_chat_completion(self, messages, *, temperature=0.3, max_tokens=500):
        self.called = True
        return "fallback reply"


def test_fallback_ai_client_uses_fallback_when_primary_fails() -> None:
    fallback = RecordingClient()
    client = FallbackAIClient(FailingClient(), fallback)

    reply = asyncio.run(client.create_chat_completion([]))

    assert reply == "fallback reply"
    assert fallback.called is True
