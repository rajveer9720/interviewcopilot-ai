"""Sessions domain — Pydantic schemas."""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Literal


class SessionCreateRequest(BaseModel):
    mode: Literal["practice", "interview", "review"]
    title: str | None = None
    target_role: str | None = None
    target_company: str | None = None
    resume_id: UUID | None = None


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    mode: str
    title: str | None
    target_role: str | None
    target_company: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_secs: int | None
    total_questions: int

    class Config:
        from_attributes = True


class TranscriptResponse(BaseModel):
    id: UUID
    session_id: UUID
    speaker: str | None
    content: str
    confidence: float | None
    is_question: bool
    start_time_ms: int | None
    end_time_ms: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class AIResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    provider: str | None
    model_name: str | None
    response_text: str | None
    response_type: str | None
    latency_ms: int | None
    cost_usd: float | None
    created_at: datetime

