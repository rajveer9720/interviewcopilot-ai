"""
Characterization tests for `LLMRouter.route` (backend/ai/router.py). Pins
today's fallback-chain behavior — try each provider once in tier order, no
retry within a provider, raise if all fail — before Phase 5 adds a hybrid
question-detector fallback that reuses this same router.
"""

from unittest.mock import AsyncMock

import pytest

from backend.ai.router import LLMRouter


async def _tokens(*values: str):
    for v in values:
        yield v


@pytest.mark.usefixtures("fake_redis")
async def test_pro_tier_uses_openai_first_and_succeeds():
    router = LLMRouter()
    router.providers["openai"].complete = AsyncMock(return_value=_tokens("Hello"))
    router.providers["gemini"].complete = AsyncMock(
        side_effect=AssertionError("gemini should not be called when openai succeeds")
    )

    result, provider_name = await router.route("prompt", "user1", stream=True, plan_tier="pro")

    assert provider_name == "openai"
    assert [t async for t in result] == ["Hello"]


@pytest.mark.usefixtures("fake_redis")
async def test_falls_back_to_gemini_when_openai_fails():
    router = LLMRouter()
    router.providers["openai"].complete = AsyncMock(side_effect=RuntimeError("openai down"))
    router.providers["gemini"].complete = AsyncMock(return_value=_tokens("Hi"))

    result, provider_name = await router.route("prompt", "user1", stream=True, plan_tier="pro")

    assert provider_name == "gemini"
    assert [t async for t in result] == ["Hi"]


@pytest.mark.usefixtures("fake_redis")
async def test_free_tier_only_ever_tries_gemini():
    router = LLMRouter()
    router.providers["gemini"].complete = AsyncMock(return_value=_tokens("ok"))
    router.providers["openai"].complete = AsyncMock(
        side_effect=AssertionError("openai should not be tried on the free tier")
    )

    _, provider_name = await router.route("prompt", "user1", stream=True, plan_tier="free")

    assert provider_name == "gemini"


async def test_raises_when_every_provider_in_the_chain_fails():
    router = LLMRouter()
    router.providers["openai"].complete = AsyncMock(side_effect=RuntimeError("openai down"))
    router.providers["gemini"].complete = AsyncMock(side_effect=RuntimeError("gemini down"))

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await router.route("prompt", "user1", stream=True, plan_tier="pro")
