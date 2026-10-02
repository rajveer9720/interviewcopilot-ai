"""Authenticated, bounded and ordered live audio pipeline."""
import asyncio
import base64
import binascii
import json
import logging
import math
import time
import uuid
from array import array
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.config import settings
from backend.core.security import decode_access_token
from backend.core.database import AsyncSessionFactory
from backend.sessions.models import Session, AIResponse
from backend.sessions.service import SessionService
from backend.transcripts.whisper_client import WhisperClient
from backend.ai.router import LLMRouter
from backend.ai.prompt_builder import PromptBuilder
from backend.auth.models import User

router = APIRouter()
logger = logging.getLogger(__name__)
SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2
MIN_UTTERANCE_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 0.35)
SILENCE_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 0.65)
MAX_UTTERANCE_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * 20
MAX_MESSAGE_CHARS = 100_000
MAX_CHUNK_BYTES = 32_000
QUESTION_MARKERS = [
    "tell me", "describe", "explain", "what", "how", "why", "when",
    "can you", "could you", "would you", "have you", "do you",
    "walk me through", "give me an example",
    "difference between", "differentiate between", "distinguish between",
    "compare and contrast", "advantages of", "disadvantages of",
    "pros and cons of", "define ", " vs ", " versus ",
    "kya", "kaise", "kyun", "kyu", "kab", "kaun", "kahan", "kitna", "kitne",
    "batao", "bataiye", "samjhao", "samjhaiye",
    "क्या", "कैसे", "क्यों", "कब", "कौन", "कहाँ", "कितना", "कितने",
    "बताओ", "बताइए", "समझाओ", "समझाइए",
]

whisper = WhisperClient()
llm_router = LLMRouter()
prompt_builder = PromptBuilder()
SPEECH_RMS_THRESHOLD = 250


async def _authorized_session(session_id: str, user_id: str):
    async with AsyncSessionFactory() as db:
        user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
        session = await db.scalar(select(Session).where(
            Session.id == uuid.UUID(session_id), Session.user_id == uuid.UUID(user_id)))
        if not user or not user.is_active or not session or session.status != "active":
            return None
        return user.plan_tier


@router.websocket("/ws/session/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.CORS_ORIGINS:
        await websocket.close(code=4003, reason="Origin not allowed")
        return
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        if len(raw) > 4096:
            raise ValueError("Authentication message too large")
        credentials = json.loads(raw)
        if credentials.get("type") != "authenticate":
            raise ValueError("Authentication required")
        token = credentials["token"]
        user_id = decode_access_token(token)["sub"]
        plan_tier = await _authorized_session(session_id, user_id)
    except Exception:
        await websocket.close(code=4001, reason="Invalid credentials or session")
        return
    if plan_tier is None:
        await websocket.close(code=4003, reason="Session unavailable")
        return
    await _send(websocket, {"type": "connected", "session_id": session_id})
    queue = asyncio.Queue(maxsize=4)
    history = []
    partial_question = []
    async def process_queue():
        while True:
            audio, speaker, final = await queue.get()
            try:
                await asyncio.wait_for(_process_audio_chunk(
                    websocket, session_id, user_id, audio, plan_tier, speaker, history,
                    partial_question, final), 50)
            except asyncio.TimeoutError:
                partial_question.clear()
                await _send(websocket, {"type": "error", "message": "Answer timed out. Please repeat the question."})
            finally:
                queue.task_done()
    worker = asyncio.create_task(process_queue())
    buffer = bytearray()
    pre_roll = bytearray()
    silence = 0
    speaking = False
    speaker = "interviewer"
    async def enqueue(final=True):
        nonlocal silence, speaking
        if speaking and (len(buffer) >= MIN_UTTERANCE_BYTES or final):
            if queue.full():
                await _send(websocket, {"type": "error", "message": "Processing is busy. Please pause and repeat the last question."})
            else:
                queue.put_nowait((bytes(buffer), speaker, final))
        buffer.clear()
        silence = 0
        speaking = not final
    try:
        while True:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=45)
            try:
                if len(raw) > MAX_MESSAGE_CHARS:
                    raise ValueError("Message too large")
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError("Invalid message")
                kind = msg.get("type")
                if kind == "audio_chunk":
                    audio = base64.b64decode(msg["data"], validate=True)
                    if not audio or len(audio) > MAX_CHUNK_BYTES or len(audio) % 2:
                        raise ValueError("Invalid audio chunk")
                    if _has_speech(audio):
                        if not speaking:
                            buffer.extend(pre_roll)
                            pre_roll.clear()
                        speaking = True
                        silence = 0
                    elif speaking:
                        silence += len(audio)
                    else:
                        pre_roll.extend(audio)
                        del pre_roll[:-6400]
                        continue
                    buffer.extend(audio)
                    if silence >= SILENCE_BYTES or len(buffer) >= MAX_UTTERANCE_BYTES:
                        await enqueue(final=silence >= SILENCE_BYTES)
                elif kind == "capture_config":
                    await enqueue()
                    pre_roll.clear()
                    speaker = "interviewer" if msg.get("source") == "system" else "user"
                elif kind == "audio_pause":
                    await enqueue()
                    pre_roll.clear()
                elif kind == "session_end":
                    await enqueue()
                    await _send(websocket, {"type": "session_ending"})
                    await asyncio.wait_for(queue.join(), timeout=55)
                    async with AsyncSessionFactory() as db:
                        await SessionService(db).end_session(session_id, user_id)
                        await db.commit()
                    await _send(websocket, {"type": "session_ended"})
                    await websocket.close(code=1000)
                    break
                elif kind == "ping":
                    await _send(websocket, {"type": "pong"})
                else:
                    raise ValueError("Unknown message type")
            except (ValueError, KeyError, TypeError, binascii.Error):
                await _send(websocket, {"type": "error", "message": "Invalid audio message."})
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        await websocket.close(code=4008, reason="Connection or processing timed out")
    except Exception:
        logger.exception("Live session failed: session=%s", session_id)
        await _send(websocket, {"type": "error", "message": "Session connection failed. Please reconnect."})
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


async def _process_audio_chunk(websocket, session_id, user_id, audio_bytes, plan_tier,
                               speaker="interviewer", history=None, partial_question=None,
                               final=True):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    try:
        result = await whisper.transcribe(audio_bytes) if len(audio_bytes) >= 1000 else {}
        text = (result or {}).get("text", "").strip()
        if partial_question is not None:
            if text:
                partial_question.append(text)
            if sum(len(part) for part in partial_question) > 16000:
                raise RuntimeError("Question is too long")
            if not final:
                if text:
                    await _send(websocket, {"type": "transcript", "text": text, "is_final": False,
                        "speaker": speaker, "is_question": False})
                return
            text = " ".join(partial_question)
            partial_question.clear()
        if not text:
            return
        is_question = _detect_question(text)
        await _send(websocket, {"type": "transcript", "text": text, "is_final": True,
            "speaker": speaker, "confidence": result.get("confidence", 1), "is_question": is_question})
        async with AsyncSessionFactory() as db:
            transcript = await SessionService(db).save_transcript(
                session_id=uuid.UUID(session_id), content=text, speaker=speaker,
                confidence=result.get("confidence", 1), is_question=is_question)
            transcript_id = transcript.id
            await db.commit()
        if not is_question:
            if history is not None:
                history.append("Heard: " + text)
                del history[:-6]
            return
        await _send(websocket, {"type": "question_detected", "text": text, "request_id": request_id})
        prompt = await prompt_builder.build(question=text, user_id=user_id)
        if history:
            prompt += "\nRecent conversation (context only):\n" + "\n".join(history)[-2000:]
        tokens, provider = await llm_router.route(prompt, user_id, stream=True, plan_tier=plan_tier)
        full_text = ""
        first_token_ms = None
        try:
            async for token in tokens:
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - started) * 1000)
                full_text += token
                await _send(websocket, {"type": "ai_suggestion", "token": token,
                    "provider": provider, "request_id": request_id})
        finally:
            await tokens.aclose()
        if not full_text.strip():
            raise RuntimeError("Empty answer")
        async with AsyncSessionFactory() as db:
            db.add(AIResponse(session_id=uuid.UUID(session_id), transcript_id=transcript_id,
                provider=provider, response_text=full_text, response_type="answer",
                latency_ms=first_token_ms))
            session = await db.get(Session, uuid.UUID(session_id))
            session.total_questions += 1
            await db.commit()
        if history is not None:
            history.extend(["Question: " + text, "Answer: " + full_text])
            del history[:-6]
        await _send(websocket, {"type": "ai_complete", "full_text": full_text,
            "provider": provider, "request_id": request_id, "first_token_ms": first_token_ms})
        logger.info("Answer completed: session=%s first_token_ms=%s", session_id, first_token_ms)
    except Exception:
        if partial_question is not None:
            partial_question.clear()
        logger.exception("Audio processing failed: session=%s", session_id)
        await _send(websocket, {"type": "error", "request_id": request_id,
            "message": "Could not process this question. Please repeat or try again."})


def _detect_question(text: str) -> bool:
    text_lower = text.lower().strip()
    return text_lower.endswith("?") or any(
        marker in text_lower for marker in QUESTION_MARKERS
    )


def _has_speech(pcm_bytes: bytes) -> bool:
    if len(pcm_bytes) < BYTES_PER_SAMPLE:
        return False
    samples = array("h")
    samples.frombytes(pcm_bytes[: len(pcm_bytes) - len(pcm_bytes) % BYTES_PER_SAMPLE])
    if not samples:
        return False
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    return rms >= SPEECH_RMS_THRESHOLD


async def _send(ws: WebSocket, data: dict):
    await ws.send_text(json.dumps(data))
