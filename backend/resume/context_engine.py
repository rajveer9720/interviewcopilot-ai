"""
Resume context engine.

Matches a detected interview question type to the relevant sections of a
candidate's active resume, so the LLM coaching prompt can be personalized.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.resume.models import Resume

# Which parsed-resume sections are most relevant per question type.
SECTION_MAP: dict[str, tuple[str, ...]] = {
    "behavioral": ("experience", "projects", "summary"),
    "technical": ("skills", "projects"),
    "general": ("summary", "skills", "experience"),
}


class ResumeContextEngine:
    """Builds a text context block from a candidate's active resume."""

    async def build_context(
        self,
        db: AsyncSession,
        user_id: str,
        question_type: str,
    ) -> str | None:
        resume = await self._get_active_resume(db, user_id)
        if not resume or not resume.parsed_data:
            return None

        sections = self._select_sections(resume.parsed_data, question_type)
        return self._format_context_block(sections)

    async def _get_active_resume(self, db: AsyncSession, user_id: str) -> Resume | None:
        result = await db.execute(
            select(Resume)
            .where(Resume.user_id == uuid.UUID(str(user_id)), Resume.is_active.is_(True))
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _select_sections(self, parsed_data: dict, question_type: str) -> dict:
        keys = SECTION_MAP.get(question_type, SECTION_MAP["general"])
        return {k: parsed_data[k] for k in keys if parsed_data.get(k)}

    def _format_context_block(self, sections: dict) -> str | None:
        if not sections:
            return None
        parts = []
        for key, value in sections.items():
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                value = ", ".join(value)
            parts.append(f"{label}: {value}")
        return "\n".join(parts)
