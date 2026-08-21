"""Google Gemini Pro provider implementation."""

import asyncio
from typing import AsyncGenerator

import google.generativeai as genai

from backend.ai.providers.base import LLMProvider, SYSTEM_PROMPT
from backend.config import settings


class GeminiProvider(LLMProvider):

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> str | AsyncGenerator[str, None]:
        generation_config = genai.GenerationConfig(max_output_tokens=max_tokens, temperature=0.7)

        if stream:
            async def _stream_tokens() -> AsyncGenerator[str, None]:
                response = await asyncio.to_thread(
                    self._model.generate_content,
                    prompt,
                    generation_config=generation_config,
                    stream=True,
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text

            return _stream_tokens()
        else:
            response = await asyncio.to_thread(
                self._model.generate_content,
                prompt,
                generation_config=generation_config,
            )
            return response.text

    async def health_check(self) -> bool:
        try:
            await asyncio.to_thread(
                self._model.generate_content,
                "ping",
                generation_config=genai.GenerationConfig(max_output_tokens=5),
            )
            return True
        except Exception:
            return False

    @property
    def cost_per_1k_tokens(self) -> float:
        return 0.00075  # Gemini 1.5 Pro: $0.75 / 1M tokens

    @property
    def provider_name(self) -> str:
        return "gemini"
