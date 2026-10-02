"""Exercise the actual live pipeline with isolated storage and fake providers."""
import asyncio
import base64
import json
import uuid
from array import array
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi import WebSocketDisconnect

from backend.auth.models import User
from backend.auth.dependencies import get_current_user
from backend.main import app
from backend.sessions.models import Session, AIResponse, Transcript
from backend.sessions import ws_handler as live


class Socket:
    def __init__(self, messages=(), origin="http://localhost:5173"):
        self.headers = {"origin": origin}
        self.messages = iter([{"type": "authenticate", "token": "test"}, *messages])
        self.sent = []
        self.accepted = False
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=""):
        self.close_code = code

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def receive_text(self):
        await asyncio.sleep(0)
        try:
            return json.dumps(next(self.messages))
        except StopIteration:
            raise WebSocketDisconnect()


@pytest.fixture
async def owned_session(db_session, monkeypatch):
    owner = User(email="owner@example.com", hashed_password="unused")
    other = User(email="other@example.com", hashed_password="unused")
    db_session.add_all([owner, other])
    await db_session.flush()
    session = Session(user_id=owner.id, mode="interview")
    db_session.add(session)
    await db_session.commit()
    monkeypatch.setattr(live, "AsyncSessionFactory", async_sessionmaker(
        db_session.bind, expire_on_commit=False))
    monkeypatch.setattr(live, "decode_access_token", lambda _: {"sub": str(owner.id)})
    return owner, other, session


def chunk(samples):
    return {"type": "audio_chunk", "data": base64.b64encode(array("h", samples).tobytes()).decode()}


async def test_websocket_rejects_other_users_session(owned_session, monkeypatch):
    owner, other, session = owned_session
    monkeypatch.setattr(live, "decode_access_token", lambda _: {"sub": str(other.id)})
    socket = Socket()
    await live.websocket_session(socket, str(session.id))
    assert not socket.sent
    assert socket.close_code == 4003


async def test_websocket_rejects_untrusted_origin(owned_session):
    _, _, session = owned_session
    socket = Socket(origin="https://untrusted.example")
    await live.websocket_session(socket, str(session.id))
    assert not socket.accepted
    assert socket.close_code == 4003


async def test_websocket_rejects_invalid_token(owned_session, monkeypatch):
    _, _, session = owned_session
    def invalid(_):
        raise ValueError("bad token")
    monkeypatch.setattr(live, "decode_access_token", invalid)
    socket = Socket()
    await live.websocket_session(socket, str(session.id))
    assert socket.close_code == 4001
    assert not socket.sent


async def test_live_questions_are_ordered_saved_and_drained(owned_session, db_session, monkeypatch):
    owner, _, session = owned_session
    monkeypatch.setattr(live.whisper, "transcribe", AsyncMock(side_effect=[
        {"text": "What is a queue?", "confidence": 0.9},
        {"text": "How does it differ from a stack?", "confidence": 0.9},
    ]))
    prompts = []
    async def build(**kwargs):
        return kwargs["question"]
    async def route(prompt, *args, **kwargs):
        prompts.append(prompt)
        async def tokens():
            yield "Answer "
            await asyncio.sleep(0)
            yield str(len(prompts))
        return tokens(), "gemini"
    monkeypatch.setattr(live.prompt_builder, "build", build)
    monkeypatch.setattr(live.llm_router, "route", route)
    socket = Socket([
        {"type": "capture_config", "source": "system"},
        chunk([1000] * 8000), chunk([0] * 11000),
        chunk([1000] * 8000), {"type": "session_end"},
    ])
    await live.websocket_session(socket, str(session.id))
    completions = [m for m in socket.sent if m["type"] == "ai_complete"]
    assert [m["full_text"] for m in completions] == ["Answer 1", "Answer 2"]
    assert len({m["request_id"] for m in completions}) == 2
    ids = [m["request_id"] for m in socket.sent if m["type"] == "ai_suggestion"]
    assert ids == [completions[0]["request_id"]] * 2 + [completions[1]["request_id"]] * 2
    assert "What is a queue?" in prompts[1]
    assert "Answer 1" in prompts[1]
    assert socket.sent[-1]["type"] == "session_ended"
    assert socket.close_code == 1000
    await db_session.refresh(session)
    stored_session = session
    assert stored_session.status == "completed"
    assert stored_session.total_questions == 2
    responses = (await db_session.scalars(select(AIResponse))).all()
    assert len(responses) == 2
    assert all(r.provider == "gemini" and r.latency_ms is not None for r in responses)
    transcripts = (await db_session.scalars(select(Transcript))).all()
    assert all(t.speaker == "interviewer" for t in transcripts)


async def test_invalid_audio_and_silence_never_call_transcriber(owned_session, monkeypatch):
    _, _, session = owned_session
    transcribe = AsyncMock()
    monkeypatch.setattr(live.whisper, "transcribe", transcribe)
    socket = Socket([
        {"type": "audio_chunk", "data": "not base64!"},
        chunk([1000] * 17000),
        chunk([0] * 11000), chunk([0] * 11000),
        {"type": "session_end"},
    ])
    await live.websocket_session(socket, str(session.id))
    transcribe.assert_not_awaited()
    assert len([m for m in socket.sent if m["type"] == "error"]) == 2


async def test_processing_error_is_visible_and_session_can_end(owned_session, monkeypatch):
    _, _, session = owned_session
    monkeypatch.setattr(live.whisper, "transcribe", AsyncMock(side_effect=RuntimeError("secret error")))
    socket = Socket([chunk([1000] * 8000), {"type": "session_end"}])
    await live.websocket_session(socket, str(session.id))
    errors = [m for m in socket.sent if m["type"] == "error"]
    assert errors and "secret error" not in errors[0]["message"]
    assert socket.sent[-1]["type"] == "session_ended"


async def test_long_question_is_combined_before_answering(owned_session, monkeypatch):
    _, _, session = owned_session
    monkeypatch.setattr(live, "MAX_UTTERANCE_BYTES", 16000)
    monkeypatch.setattr(live.whisper, "transcribe", AsyncMock(side_effect=[
        {"text": "How would you design a service", "confidence": 0.9},
        {"text": "for millions of concurrent users?", "confidence": 0.9},
    ]))
    build = AsyncMock(return_value="full question")
    monkeypatch.setattr(live.prompt_builder, "build", build)
    async def route(*args, **kwargs):
        async def tokens():
            yield "Combined answer"
        return tokens(), "gemini"
    monkeypatch.setattr(live.llm_router, "route", route)
    socket = Socket([chunk([1000] * 8000), chunk([1000] * 4000), {"type": "session_end"}])
    await live.websocket_session(socket, str(session.id))
    assert build.await_args.kwargs["question"] == "How would you design a service for millions of concurrent users?"
    assert len([m for m in socket.sent if m["type"] == "ai_complete"]) == 1


@pytest.mark.parametrize("suffix", ["transcripts", "feedback", "feedback/generate"])
async def test_rest_session_data_is_private(owned_session, client, suffix):
    _, other, session = owned_session
    app.dependency_overrides[get_current_user] = lambda: other
    if suffix == "transcripts":
        response = await client.get(f"/api/v1/sessions/{session.id}/transcripts")
    elif suffix == "feedback":
        response = await client.get(f"/api/v1/feedback/sessions/{session.id}/feedback")
    else:
        response = await client.post(f"/api/v1/feedback/sessions/{session.id}/feedback/generate")
    assert response.status_code == 404


async def test_logout_revokes_refresh_token(client, fake_redis):
    await fake_redis.set("refresh:test-id", "user:test-value")
    client.cookies.set("refresh_token", "test-id:test-value")
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert await fake_redis.get("refresh:test-id") is None


async def test_refresh_rejects_cross_site_origin(client):
    response = await client.post("/api/v1/auth/refresh", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
