import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.feedback.models import SessionFeedback
from backend.main import app
from backend.sessions.models import AIResponse, Session
from backend.sessions.practice import generate_review, practice_state


async def interview(db, answered=True, completed=False):
    user = User(email="voice@example.com", hashed_password="unused", plan_tier="free")
    db.add(user)
    await db.flush()
    session = Session(user_id=user.id, mode="practice", status="completed" if completed else "active")
    db.add(session)
    await db.flush()
    row = AIResponse(session_id=session.id, response_type="practice_turn", response_text=json.dumps({
        "question": "Explain indexes", "answer": "They speed up reads" if answered else None,
        "feedback": "AI SAMPLE FEEDBACK" if answered else None,
    }))
    db.add(row)
    await db.flush()
    return user, session, row


async def test_transcription_only_returns_editable_draft(client, db_session):
    user, session, row = await interview(db_session, answered=False)
    app.dependency_overrides[get_current_user] = lambda: user
    path = f"/api/v1/sessions/{session.id}/practice/transcribe?question_id={row.id}"
    with patch("backend.transcripts.whisper_client.WhisperClient") as whisper:
        whisper.return_value.transcribe = AsyncMock(return_value={"text": " My recorded answer "})
        response = await client.post(path, content=b"\x01\x00" * 16000,
                                     headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 200
    assert response.json()["text"] == "My recorded answer"
    assert json.loads(row.response_text)["answer"] is None


async def test_audio_validation_and_silence(client, db_session):
    user, session, row = await interview(db_session, answered=False)
    app.dependency_overrides[get_current_user] = lambda: user
    path = f"/api/v1/sessions/{session.id}/practice/transcribe?question_id={row.id}"
    headers = {"Content-Type": "application/octet-stream"}
    with patch("backend.transcripts.whisper_client.WhisperClient") as whisper:
        whisper.return_value.transcribe = AsyncMock(return_value={"text": ""})
        assert (await client.post(path, content=b"xx", headers=headers)).status_code == 422
        assert (await client.post(path, content=b"x" * (3840000 + 2), headers=headers)).status_code == 413
        assert (await client.post(path, content=b"x" * 16000)).status_code == 415
        assert (await client.post(path, content=b"x" * 16000, headers=headers)).status_code == 422
        assert whisper.return_value.transcribe.call_count == 1


async def test_audio_rejects_completed_or_foreign_sessions(client, db_session):
    user, session, row = await interview(db_session, answered=False, completed=True)
    app.dependency_overrides[get_current_user] = lambda: user
    path = f"/api/v1/sessions/{session.id}/practice/transcribe?question_id={row.id}"
    assert (await client.post(path, content=b"x" * 16000)).status_code == 409
    other = User(email="foreign@example.com", hashed_password="unused")
    db_session.add(other)
    await db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: other
    assert (await client.post(path, content=b"x" * 16000)).status_code == 404
    assert (await client.post(f"/api/v1/sessions/{session.id}/practice/review")).status_code == 404


VALID_REVIEW = {"overall": 5.5, "communication": 6, "technical": 5,
                "strengths": ["Identified read performance"], "improvements": ["Explain write overhead"],
                "report": "A clear starting point, but explain index structure and write trade-offs. Only one short answer was available."}


async def test_review_is_saved_and_excludes_ai_answers(db_session):
    user, session, _ = await interview(db_session, completed=True)
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = AsyncMock(return_value=(json.dumps(VALID_REVIEW), "gemini"))
        review = await generate_review(db_session, session, user)
        again = await generate_review(db_session, session, user)
        assert router.return_value.route.call_count == 1
        prompt = router.return_value.route.call_args.args[0]
    assert "They speed up reads" in prompt
    assert "AI SAMPLE FEEDBACK" not in prompt
    assert review.id == again.id
    assert review.overall_score == 5.5
    assert review.confidence_score is None
    assert (await practice_state(db_session, session))["review"]["scores"]["overall"] == 5.5


@pytest.mark.parametrize("raw", ['{"overall":99}', json.dumps({**VALID_REVIEW, "technical": 99})])
async def test_invalid_review_never_creates_default_scores(db_session, raw):
    user, session, _ = await interview(db_session, completed=True)
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = AsyncMock(return_value=(raw, "gemini"))
        with pytest.raises(HTTPException) as error:
            await generate_review(db_session, session, user)
    assert error.value.status_code == 503
    assert await db_session.scalar(select(SessionFeedback)) is None


async def test_no_answer_does_not_get_review(db_session):
    user, session, _ = await interview(db_session, answered=False, completed=True)
    with pytest.raises(HTTPException) as error:
        await generate_review(db_session, session, user)
    assert error.value.status_code == 422
