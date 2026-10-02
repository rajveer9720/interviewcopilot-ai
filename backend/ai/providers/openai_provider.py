"""OpenAI GPT-4o provider implementation."""

from openai import AsyncOpenAI
from typing import AsyncGenerator

from backend.ai.providers.base import LLMProvider, SYSTEM_PROMPT
from backend.config import settings


class OpenAIProvider(LLMProvider):

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=20, max_retries=1)
        self.model = settings.OPENAI_MODEL

    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> str | AsyncGenerator[str, None]:
        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            stream=stream,
        )

        if stream:
            response = await self.client.chat.completions.create(**kwargs)

            async def _stream_tokens() -> AsyncGenerator[str, None]:
                async for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta

            return _stream_tokens()
        else:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    @property
    def cost_per_1k_tokens(self) -> float:
        return 0.005  # GPT-4o input: $5 / 1M tokens

    @property
    def provider_name(self) -> str:
        return "openai"
