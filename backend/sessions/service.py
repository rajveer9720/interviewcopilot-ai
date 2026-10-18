"""Sessions domain — service layer."""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException
from datetime import datetime, timezone

from backend.sessions.models import Session, Transcript
from backend.sessions.schemas import SessionCreateRequest
from backend.resume.models import Resume


class SessionService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, user_id: str, payload: SessionCreateRequest) -> Session:
        if payload.resume_id:
            resume = await self.db.scalar(select(Resume).where(
                Resume.id == payload.resume_id, Resume.user_id == uuid.UUID(str(user_id))))
            if not resume:
                raise HTTPException(status_code=404, detail="Resume not found.")
        session = Session(
            user_id=uuid.UUID(str(user_id)),
            mode=payload.mode,
            title=payload.title,
            target_role=payload.target_role,
            target_company=payload.target_company,
            resume_id=payload.resume_id,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(self, session_id: str, user_id: str) -> Session:
        result = await self.db.execute(
            select(Session).where(
                Session.id == uuid.UUID(str(session_id)),
                Session.user_id == uuid.UUID(str(user_id)),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return session

    async def list_sessions(self, user_id: str, limit: int = 20, offset: int = 0) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == uuid.UUID(str(user_id)))
            .order_by(desc(Session.started_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def end_session(self, session_id: str, user_id: str) -> Session:
        session = await self.get_session(session_id, user_id)
        session = await self.db.scalar(select(Session).where(
            Session.id == session.id).with_for_update().execution_options(populate_existing=True))
        if session.status == "completed":
            return session
        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.ended_at = now
        if session.started_at:
            session.duration_secs = int((now - session.started_at.replace(tzinfo=timezone.utc)).total_seconds())
        await self.db.flush()
        return session

    async def save_transcript(
        self,
        session_id: str,
        content: str,
        speaker: str = "user",
        confidence: float | None = None,
        is_question: bool = False,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> Transcript:
        transcript = Transcript(
            session_id=session_id,
            content=content,
            speaker=speaker,
            confidence=confidence,
            is_question=is_question,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
        )
        self.db.add(transcript)
        await self.db.flush()
        return transcript
