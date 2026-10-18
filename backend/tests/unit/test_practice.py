import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend.auth.models import User
from backend.sessions.models import Session
from backend.sessions.practice import advance, practice_state
from backend.sessions.schemas import PracticeAction


async def setup_practice(db):
    user = User(email="practice@example.com", hashed_password="unused", plan_tier="free")
    db.add(user)
    await db.flush()
    session = Session(user_id=user.id, mode="practice", target_role="Backend Engineer")
    db.add(session)
    await db.flush()
    return user, session


async def test_practice_persists_answers_and_passes_history(db_session):
    user, session = await setup_practice(db_session)
    route = AsyncMock(side_effect=[
        (json.dumps({"question": "How do database indexes work?"}), "gemini"),
        (json.dumps({"feedback": "Strengths: clear example. Gaps: write costs. Try next: explain trade-offs."}), "gemini"),
        (json.dumps({"question": "What happens to write performance?"}), "gemini"),
    ])
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = route
        state = await advance(db_session, session, user, PracticeAction(action="start"))
        question_id = state["turns"][0]["id"]
        await advance(db_session, session, user, PracticeAction(
            action="answer", question_id=question_id, answer="Indexes speed up reads using a search structure."))
        # A repeated network request must not create duplicate answers or spend another call.
        await advance(db_session, session, user, PracticeAction(
            action="answer", question_id=question_id, answer="duplicate"))
        state = await advance(db_session, session, user, PracticeAction(action="next", question_id=question_id))
    assert len(state["turns"]) == 2
    assert state["turns"][0]["answer"].startswith("Indexes speed")
    assert route.call_count == 3
    assert "Indexes speed up reads" in route.call_args.args[0]
    assert "Backend Engineer" in route.call_args.args[0]
    assert (await practice_state(db_session, session))["turns"] == state["turns"]


async def test_invalid_generation_does_not_save_question(db_session):
    user, session = await setup_practice(db_session)
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = AsyncMock(return_value=("invalid JSON", "gemini"))
        with pytest.raises(HTTPException) as error:
            await advance(db_session, session, user, PracticeAction(action="start"))
    assert error.value.status_code == 503
    assert (await practice_state(db_session, session))["turns"] == []
    assert session.total_questions == 0


async def test_practice_rejects_unanswered_next_and_stale_question(db_session):
    user, session = await setup_practice(db_session)
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = AsyncMock(return_value=('{"question":"Explain caching."}', "gemini"))
        state = await advance(db_session, session, user, PracticeAction(action="start"))
    with pytest.raises(HTTPException) as error:
        await advance(db_session, session, user, PracticeAction(action="next", question_id=state["turns"][0]["id"]))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        await advance(db_session, session, user, PracticeAction(action="answer", answer="stale"))
    session.status = "completed"
    await db_session.flush()
    with pytest.raises(HTTPException):
        await advance(db_session, session, user, PracticeAction(action="start"))


async def test_practice_api_checks_ownership(client, db_session):
    from backend.auth.dependencies import get_current_user
    from backend.main import app

    user, session = await setup_practice(db_session)
    other = User(email="other-practice@example.com", hashed_password="unused")
    db_session.add(other)
    await db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: other
    path = f"/api/v1/sessions/{session.id}/practice"
    assert (await client.get(path)).status_code == 404
    assert (await client.post(path, json={"action": "start"})).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: user
    assert (await client.get(path)).json()["turns"] == []
    with patch("backend.sessions.practice.LLMRouter") as router:
        router.return_value.route = AsyncMock(return_value=('{"question":"Explain caching."}', "gemini"))
        response = await client.post(path, json={"action": "start"})
    assert response.status_code == 200
    assert response.json()["turns"][0]["question"] == "Explain caching."
