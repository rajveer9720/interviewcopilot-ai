"""Abstract base class for all LLM providers."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


SYSTEM_PROMPT = """You are InterviewCopilot, an expert interview coach for software engineers.

When given an interview question:
1. Provide a concise, structured answer framework (STAR method for behavioral, clear steps for technical)
2. Include 2-3 key talking points the candidate should cover
3. Highlight what makes a strong answer for this type of question
4. Keep your response focused and actionable — under 250 words

You coach candidates to improve their interviewing skills through practice and structured feedback.
Never answer on the candidate's behalf — guide them on HOW to answer effectively.
"""


class LLMProvider(ABC):

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        stream: bool = True,
        max_tokens: int = 500,
    ) -> str | AsyncGenerator[str, None]:
        """Generate a completion. If stream=True, returns an AsyncGenerator of tokens."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable and operational."""
        ...

    @property
    @abstractmethod
    def cost_per_1k_tokens(self) -> float:
        """Estimated USD cost per 1000 tokens for cost tracking."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
