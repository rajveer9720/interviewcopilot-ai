from unittest.mock import AsyncMock

import pytest

from backend.ai.router import LLMRouter


async def broken_stream():
    raise RuntimeError("provider failed before output")
    yield ""


async def good_stream():
    yield "Working answer"


@pytest.mark.usefixtures("fake_redis")
async def test_fallback_when_stream_fails_before_first_token():
    router = LLMRouter()
    router.providers["openai"].complete = AsyncMock(return_value=broken_stream())
    router.providers["gemini"].complete = AsyncMock(return_value=good_stream())
    tokens, provider = await router.route("question", "user", plan_tier="pro")
    assert provider == "gemini"
    assert [token async for token in tokens] == ["Working answer"]


async def test_usage_cache_failure_does_not_discard_answer():
    router = LLMRouter()
    router.providers["gemini"].complete = AsyncMock(return_value=good_stream())
    router._track_usage = AsyncMock(side_effect=RuntimeError("Redis down"))
    tokens, provider = await router.route("question", "user")
    assert provider == "gemini"
    assert [token async for token in tokens] == ["Working answer"]
