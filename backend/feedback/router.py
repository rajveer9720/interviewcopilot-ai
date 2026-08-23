"""Feedback domain — FastAPI router."""

import asyncio
import logging

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.feedback.models import SessionFeedback
from backend.feedback.service import FeedbackService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sessions/{session_id}/feedback")
async def get_feedback(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionFeedback).where(SessionFeedback.session_id == session_id)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        return {"status": "pending", "message": "Feedback is being generated."}

    return {
        "id": str(feedback.id),
        "session_id": session_id,
        "scores": {
            "overall":       feedback.overall_score,
            "communication": feedback.communication_score,
            "technical":     feedback.technical_score,
            "star_method":   feedback.star_method_score,
            "confidence":    feedback.confidence_score,
        },
        "strengths":     feedback.strengths,
        "improvements":  feedback.improvements,
        "detailed_report": feedback.detailed_report,
        "created_at":    feedback.created_at.isoformat(),
    }


@router.post("/sessions/{session_id}/feedback/generate")
async def trigger_feedback(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger feedback generation (called after session ends)."""
    background_tasks.add_task(_run_feedback, session_id)
    return {"status": "queued", "message": "Feedback generation started."}


async def _run_feedback(session_id: str):
    from backend.core.database import AsyncSessionFactory
    try:
        await asyncio.sleep(1)
        async with AsyncSessionFactory() as db:
            svc = FeedbackService(db)
            await svc.generate_feedback(session_id)
            await db.commit()
        logger.info("Manual feedback generation complete: session=%s", session_id)
    except Exception as e:
        logger.exception("Manual feedback generation failed: session=%s error=%s", session_id, e)
