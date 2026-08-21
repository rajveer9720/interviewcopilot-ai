"""Analytics domain — dashboard and history endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.sessions.models import Session
from backend.feedback.models import SessionFeedback

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Overview stats for the dashboard."""
    user_id = current_user.id
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total sessions
    total_sessions = await db.scalar(
        select(func.count(Session.id)).where(Session.user_id == user_id)
    )

    # Sessions this month
    sessions_this_month = await db.scalar(
        select(func.count(Session.id)).where(
            Session.user_id == user_id,
            Session.started_at >= thirty_days_ago,
        )
    )

    # Average score
    avg_score = await db.scalar(
        select(func.avg(SessionFeedback.overall_score))
        .join(Session, Session.id == SessionFeedback.session_id)
        .where(Session.user_id == user_id)
    )

    # Total practice time (minutes)
    total_secs = await db.scalar(
        select(func.sum(Session.duration_secs)).where(
            Session.user_id == user_id,
            Session.status == "completed",
        )
    )

    # Recent sessions
    recent = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(desc(Session.started_at))
        .limit(5)
    )

    return {
        "total_sessions":       total_sessions or 0,
        "sessions_this_month":  sessions_this_month or 0,
        "average_score":        round(avg_score or 0, 1),
        "total_practice_mins":  (total_secs or 0) // 60,
        "plan_tier":            current_user.plan_tier,
        "recent_sessions": [
            {
                "id": str(s.id),
                "title": s.title,
                "mode": s.mode,
                "status": s.status,
                "started_at": s.started_at.isoformat(),
                "duration_secs": s.duration_secs,
            }
            for s in recent.scalars().all()
        ],
    }


@router.get("/scores")
async def get_score_history(
    range_days: int = Query(30, alias="range", le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Score trend over time for chart display."""
    since = datetime.now(timezone.utc) - timedelta(days=range_days)

    result = await db.execute(
        select(
            Session.started_at,
            Session.title,
            SessionFeedback.overall_score,
            SessionFeedback.communication_score,
            SessionFeedback.technical_score,
        )
        .join(SessionFeedback, Session.id == SessionFeedback.session_id)
        .where(Session.user_id == current_user.id, Session.started_at >= since)
        .order_by(Session.started_at)
    )

    return [
        {
            "date":          row.started_at.isoformat(),
            "title":         row.title,
            "overall":       row.overall_score,
            "communication": row.communication_score,
            "technical":     row.technical_score,
        }
        for row in result
    ]
