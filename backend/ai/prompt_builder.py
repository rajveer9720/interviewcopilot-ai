"""
Context-aware prompt builder.
Enriches LLM prompts with resume context and question classification.
"""

from backend.core.redis import get_redis
from backend.core.database import AsyncSessionFactory
from backend.resume.context_engine import ResumeContextEngine
import logging

logger = logging.getLogger(__name__)

RESUME_CONTEXT_CACHE_TTL_SECONDS = 3600

BEHAVIORAL_TEMPLATE = """
Interview Question (Behavioral):
"{question}"

Candidate's Relevant Background:
{resume_context}

Write a directly usable sample answer using the STAR method
(Situation, Task, Action, Result). Use only documented experience; do not invent achievements.
Keep the answer under 200 words.
"""

TECHNICAL_TEMPLATE = """
Interview Question (Technical):
"{question}"

Candidate's Technical Background:
{resume_context}

Answer the technical question directly and accurately.
Start with the core answer, then a brief explanation and relevant example.
Keep the answer under 200 words.
"""

GENERAL_TEMPLATE = """
Interview Question:
"{question}"

Candidate Background:
{resume_context}

Provide a concise, direct sample answer.
Keep the answer under 200 words.
"""

TEMPLATES = {
    "behavioral": BEHAVIORAL_TEMPLATE,
    "technical":  TECHNICAL_TEMPLATE,
    "general":    GENERAL_TEMPLATE,
}


class PromptBuilder:

    def __init__(self):
        self.context_engine = ResumeContextEngine()

    async def build(self, question: str, user_id: str) -> str:
        question_type = self._classify_question(question)
        resume_context = await self._get_resume_context(user_id, question_type)
        template = TEMPLATES[question_type]
        return template.format(
            question=question,
            resume_context=resume_context or "No resume context available.",
        )

    def _classify_question(self, question: str) -> str:
        q = question.lower()
        behavioral = ["tell me about", "describe a time", "how did you", "give me an example",
                      "what was a situation", "have you ever", "walk me through a time"]
        technical =  ["explain", "how does", "what is", "implement", "design", "algorithm",
                      "data structure", "complexity", "optimize", "debug", "code"]
        if any(kw in q for kw in behavioral):
            return "behavioral"
        if any(kw in q for kw in technical):
            return "technical"
        return "general"

    async def _get_resume_context(self, user_id: str, question_type: str) -> str | None:
        redis_client = get_redis()
        cache_key = f"resume_context:{user_id}:{question_type}"
        try:
            cached = await redis_client.get(cache_key)
        except Exception:
            cached = None
            logger.warning("Resume cache unavailable", exc_info=True)
        if cached:
            return cached

        async with AsyncSessionFactory() as db:
            context = await self.context_engine.build_context(db, user_id, question_type)

        if context:
            try:
                await redis_client.setex(cache_key, RESUME_CONTEXT_CACHE_TTL_SECONDS, context)
            except Exception:
                logger.warning("Resume cache write failed", exc_info=True)
        return context
