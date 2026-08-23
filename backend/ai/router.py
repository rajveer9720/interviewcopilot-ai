"""
LLM Router — selects provider based on user plan tier,
tracks usage and cost, automatically falls back to next provider.
"""

import logging
import time
from typing import AsyncGenerator

from backend.ai.providers.base import LLMProvider
from backend.ai.providers.openai_provider import OpenAIProvider
from backend.ai.providers.gemini_provider import GeminiProvider
from backend.ai.response_ranker import ResponseRanker
from backend.core.redis import get_redis

logger = logging.getLogger(__name__)

TIER_PROVIDER_MAP = {
    "free":       ["gemini"],
    "pro":        ["openai", "gemini"],
    "enterprise": ["openai", "gemini"],
}


class LLMRouter:

    def __init__(self):
        self.providers: dict[str, LLMProvider] = {
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
        }
        self.ranker = ResponseRanker()

    async def route(
        self,
        prompt: str,
        user_id: str,
        stream: bool = True,
        plan_tier: str = "free",
    ) -> tuple[AsyncGenerator[str, None] | str, str]:
        provider_chain = TIER_PROVIDER_MAP.get(plan_tier, ["gemini"])
        logger.info(
            "LLM routing started: user=%s plan=%s providers=%s stream=%s",
            user_id,
            plan_tier,
            provider_chain,
            stream,
        )

        for provider_name in provider_chain:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            try:
                start_ms = int(time.time() * 1000)
                result = await provider.complete(prompt, stream=stream)
                latency_ms = int(time.time() * 1000) - start_ms

                # Track usage in Redis
                await self._track_usage(user_id, provider_name, latency_ms)

                logger.info("LLM routed to %s (latency=%dms)", provider_name, latency_ms)
                return result, provider_name

            except Exception as e:
                logger.exception(
                    "Provider %s failed for user=%s: %s. Falling back...",
                    provider_name,
                    user_id,
                    e,
                )
                continue

        raise RuntimeError("All LLM providers failed to respond.")

    async def _track_usage(self, user_id: str, provider: str, latency_ms: int):
        redis_client = get_redis()
        key = f"llm_usage:{user_id}:{provider}"
        latency_key = f"llm_latency:{user_id}:{provider}"
        await redis_client.incr(key)
        await redis_client.expire(key, 86400)
        await redis_client.lpush(latency_key, latency_ms)
        await redis_client.ltrim(latency_key, 0, 99)  # keep last 100 measurements

    async def get_provider_health(self) -> dict[str, bool]:
        return {
            name: await provider.health_check()
            for name, provider in self.providers.items()
        }
