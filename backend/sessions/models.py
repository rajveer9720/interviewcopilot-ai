"""Sessions domain — SQLAlchemy models."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, func, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # practice | interview | review
    title: Mapped[str | None] = mapped_column(String(255))
    target_role: Mapped[str | None] = mapped_column(String(255))
    target_company: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_secs: Mapped[int | None] = mapped_column(Integer)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="session")
    ai_responses: Mapped[list["AIResponse"]] = relationship(back_populates="session")
    feedback: Mapped["SessionFeedback | None"] = relationship(back_populates="session")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True)
    speaker: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str] = mapped_column(String(10), default="en")
    start_time_ms: Mapped[int | None] = mapped_column(Integer)
    end_time_ms: Mapped[int | None] = mapped_column(Integer)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="transcripts")
    ai_responses: Mapped[list["AIResponse"]] = relationship(back_populates="transcript")


class AIResponse(Base):
    __tablename__ = "ai_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True)
    transcript_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id"))
    provider: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    response_text: Mapped[str | None] = mapped_column(Text)
    response_type: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="ai_responses")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="ai_responses")
