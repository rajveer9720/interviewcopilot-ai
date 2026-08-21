"""Feedback domain — SQLAlchemy model."""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, ForeignKey, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class SessionFeedback(Base):
    __tablename__ = "session_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True)
    overall_score: Mapped[float | None] = mapped_column(Float)
    communication_score: Mapped[float | None] = mapped_column(Float)
    technical_score: Mapped[float | None] = mapped_column(Float)
    star_method_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    strengths: Mapped[list | None] = mapped_column(JSONB)
    improvements: Mapped[list | None] = mapped_column(JSONB)
    detailed_report: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="feedback")  # noqa
