"""Sessions domain — REST router."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.sessions.service import SessionService
from backend.sessions.schemas import SessionCreateRequest, SessionResponse, TranscriptResponse, PracticeAction

router = APIRouter()


@router.post("/{session_id}/practice/transcribe")
async def transcribe_practice(session_id: UUID, request: Request, question_id: UUID,
                             current_user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    from backend.sessions.practice import rows_for
    from backend.transcripts.whisper_client import WhisperClient
    from sqlalchemy import select
    from backend.sessions.models import Session
    session = await SessionService(db).get_session(session_id, str(current_user.id))
    session = await db.scalar(select(Session).where(Session.id == session.id)
                              .with_for_update().execution_options(populate_existing=True))
    if session.mode != "practice" or session.status != "active":
        raise HTTPException(409, "An active practice session is required.")
    rows = await rows_for(db, session)
    import json
    if not rows or rows[-1].id != question_id or json.loads(rows[-1].response_text)["answer"] is not None:
        raise HTTPException(409, "Question changed. Reload your practice session.")
    if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
        raise HTTPException(415, "Expected 16 kHz, mono, 16-bit PCM audio.")
    # Limit streamed bodies too, even when Content-Length is absent or incorrect.
    audio = bytearray()
    async for chunk in request.stream():
        if len(audio) + len(chunk) > 16000 * 2 * 120:
            raise HTTPException(413, "Record at most two minutes per clip.")
        audio.extend(chunk)
    if len(audio) < 16000 or len(audio) % 2:
        raise HTTPException(422, "Record at least half a second of speech.")
    try:
        result = await WhisperClient().transcribe(bytes(audio))
    except Exception:
        raise HTTPException(503, "Transcription unavailable. Retry your recording or type your answer.")
    if not (result.get("text") or "").strip():
        raise HTTPException(422, "No clear speech detected. Try recording again or type your answer.")
    return {"text": result["text"].strip()}


@router.post("/{session_id}/practice/review")
async def review_practice(session_id: UUID, current_user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    from backend.sessions.practice import generate_review, review_data
    session = await SessionService(db).get_session(session_id, str(current_user.id))
    return review_data(await generate_review(db, session, current_user))


@router.get("/{session_id}/practice")
async def get_practice(session_id: UUID, current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    from backend.sessions.practice import practice_state
    session = await SessionService(db).get_session(session_id, str(current_user.id))
    return await practice_state(db, session)


@router.post("/{session_id}/practice")
async def advance_practice(session_id: UUID, payload: PracticeAction,
                           current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    from backend.sessions.practice import advance
    session = await SessionService(db).get_session(session_id, str(current_user.id))
    return await advance(db, session, current_user, payload)


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
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.get_session(session_id, str(current_user.id))


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = SessionService(db)
    return await svc.end_session(session_id, str(current_user.id))


@router.get("/{session_id}/transcripts", response_model=list[TranscriptResponse])
async def get_transcripts(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from backend.sessions.models import Transcript
    await SessionService(db).get_session(session_id, str(current_user.id))
    result = await db.execute(
        select(Transcript).where(Transcript.session_id == session_id)
    )
    return result.scalars().all()
