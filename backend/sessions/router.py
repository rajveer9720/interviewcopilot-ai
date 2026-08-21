"""Sessions domain — REST router."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.sessions.service import SessionService
from backend.sessions.schemas import SessionCreateRequest, SessionResponse, TranscriptResponse

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.create_session(str(current_user.id), payload)


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.list_sessions(str(current_user.id), limit, offset)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.get_session(session_id, str(current_user.id))


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.end_session(session_id, str(current_user.id))


@router.get("/{session_id}/transcripts", response_model=list[TranscriptResponse])
async def get_transcripts(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from backend.sessions.models import Transcript
    result = await db.execute(
        select(Transcript).where(Transcript.session_id == session_id)
    )
    return result.scalars().all()
