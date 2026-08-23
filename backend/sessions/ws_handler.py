"""
WebSocket session handler.

Flow:
  1. Client connects, authenticates via ?token=<jwt>
  2. Client streams base64-encoded PCM audio chunks
  3. Server decodes audio → Whisper STT → transcript
  4. Server detects questions → LLM Router → streaming AI coaching
  5. Server sends events back over WebSocket in real-time
"""

import asyncio
import base64
import json
import logging
import math
from array import array
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_access_token
from backend.core.database import AsyncSessionFactory
from backend.core.redis import get_redis
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
SILENCE_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 0.8)
MAX_UTTERANCE_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 12)
SPEECH_RMS_THRESHOLD = 450

whisper = WhisperClient()
llm_router = LLMRouter()
prompt_builder = PromptBuilder()

# asyncio only holds a weak reference to a task returned by create_task(), so
# an unreferenced one (e.g. fired right before the creating coroutine returns,
# as with session_end below) can be garbage-collected mid-execution with no
# error or log. Keep a strong reference here until each task finishes.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


@router.websocket("/ws/session/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    # ── Authenticate ──────────────────────────────────────────
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except Exception as e:
        logger.exception("WS authentication failed: session=%s error=%s", session_id, e)
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WS connected: session=%s user=%s", session_id, user_id)

    plan_tier = "free"
    try:
        async with AsyncSessionFactory() as db:
            user = await db.scalar(select(User).where(User.id == user_id))
            plan_tier = user.plan_tier if user else "free"
    except Exception as e:
        logger.exception("Could not load user plan: session=%s error=%s", session_id, e)
    logger.info("WS user plan loaded: session=%s plan=%s", session_id, plan_tier)

    # Notify client
    await _send(websocket, {
        "type": "connected",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    audio_buffer = bytearray()
    silence_bytes = 0
    speech_started = False

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")
            logger.debug(
                "WS message received: session=%s type=%s bytes=%d",
                session_id,
                msg_type,
                len(raw),
            )

            if msg_type == "audio_chunk":
                # Keep collecting one utterance until the speaker pauses.
                pcm_bytes = base64.b64decode(message["data"])
                audio_buffer.extend(pcm_bytes)
                if _has_speech(pcm_bytes):
                    speech_started = True
                    silence_bytes = 0
                elif speech_started:
                    silence_bytes += len(pcm_bytes)
                logger.debug(
                    "WS audio received: session=%s bytes=%d buffer=%d silence=%d",
                    session_id,
                    len(pcm_bytes),
                    len(audio_buffer),
                    silence_bytes,
                )

                utterance_complete = (
                    speech_started
                    and len(audio_buffer) >= MIN_UTTERANCE_BYTES
                    and silence_bytes >= SILENCE_BYTES
                )
                if utterance_complete or len(audio_buffer) >= MAX_UTTERANCE_BYTES:
                    chunk = bytes(audio_buffer)
                    audio_buffer.clear()
                    silence_bytes = 0
                    speech_started = False
                    logger.info(
                        "WS utterance complete: session=%s bytes=%d reason=%s",
                        session_id,
                        len(chunk),
                        "silence" if utterance_complete else "max_duration",
                    )

                    # Offload to async worker
                    _spawn(
                        _process_audio_chunk(websocket, session_id, user_id, chunk, plan_tier)
                    )

            elif msg_type == "session_end":
                await _send(websocket, {"type": "session_ending"})
                if speech_started and len(audio_buffer) >= MIN_UTTERANCE_BYTES:
                    logger.info(
                        "WS flushing final utterance: session=%s bytes=%d",
                        session_id,
                        len(audio_buffer),
                    )
                    await _process_audio_chunk(
                        websocket, session_id, user_id, bytes(audio_buffer), plan_tier
                    )
                    audio_buffer.clear()
                # Trigger background feedback generation
                _spawn(_generate_feedback(session_id))
                break

            elif msg_type == "ping":
                await _send(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WS disconnected: session=%s", session_id)
    except Exception as e:
        logger.error("WS error: %s", e)
        await _send(websocket, {"type": "error", "message": str(e)})
    finally:
        logger.info("WS closed: session=%s", session_id)


async def _process_audio_chunk(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    audio_bytes: bytes,
    plan_tier: str,
):
    """
    1. Send to Whisper for transcription
    2. Detect if it's a question
    3. If question → build prompt → stream LLM response
    """
    try:
        # ── Step 1: Transcribe ─────────────────────────────
        logger.info("Whisper transcription started: session=%s", session_id)
        # Left on auto-detect (no forced language): forcing "hi" made Whisper
        # hallucinate fluent-looking Hindi garbage on silence/noise chunks
        # instead of returning empty/low-confidence output.
        result = await whisper.transcribe(audio_bytes)
        if not result or not result.get("text", "").strip():
            logger.warning("Whisper returned no text: session=%s result=%r", session_id, result)
            return

        text = result["text"].strip()
        confidence = result.get("confidence", 1.0)
        is_question = _detect_question(text)
        logger.info(
            "Whisper transcription complete: session=%s chars=%d is_question=%s confidence=%s",
            session_id,
            len(text),
            is_question,
            confidence,
        )

        # Send partial transcript to client
        await _send(websocket, {
            "type": "transcript",
            "text": text,
            "is_final": True,
            "speaker": "user",
            "confidence": confidence,
            "is_question": is_question,
        })

        # Save to DB
        async with AsyncSessionFactory() as db:
            svc = SessionService(db)
            transcript = await svc.save_transcript(
                session_id=session_id,
                content=text,
                confidence=confidence,
                is_question=is_question,
            )
            await db.commit()

        # ── Step 2: If question detected → LLM coaching ───
        if is_question:
            logger.info("Question detected; building AI prompt: session=%s", session_id)
            await _send(websocket, {
                "type": "question_detected",
                "text": text,
            })

            prompt = await prompt_builder.build(
                question=text,
                user_id=user_id,
            )

            full_response = ""
            logger.info("LLM request started: session=%s user=%s", session_id, user_id)
            llm_result, provider_name = await llm_router.route(
                prompt, user_id, stream=True, plan_tier=plan_tier
            )
            logger.info("LLM provider selected: session=%s provider=%s", session_id, provider_name)
            async for token in llm_result:
                full_response += token
                await _send(websocket, {
                    "type": "ai_suggestion",
                    "token": token,
                    "provider": provider_name,
                })

            logger.info(
                "LLM response complete: session=%s response_chars=%d",
                session_id,
                len(full_response),
            )
            if not full_response.strip():
                raise RuntimeError(f"{provider_name} returned an empty response")

            await _send(websocket, {
                "type": "ai_complete",
                "full_text": full_response,
            })

    except Exception as e:
        logger.exception("Audio processing error: session=%s error=%s", session_id, e)
        await _send(websocket, {"type": "error", "message": "Processing error."})


def _detect_question(text: str) -> bool:
    """
    Heuristic question detection.
    Matches anywhere in the text, not just at the start — a casual lead-in
    ("Achha ye batao, ...") means the actual question word rarely opens the
    sentence. Covers English, romanized Hindi, and Devanagari question words
    since candidates code-switch between them mid-sentence.
    """
    text_lower = text.lower().strip()
    question_markers = [
        # English
        "tell me", "describe", "explain", "what", "how", "why", "when",
        "can you", "could you", "would you", "have you", "do you",
        "walk me through", "give me an example",
        # Technical-interview phrasing that's often stated flat, without a
        # rising question tone — Whisper then won't add a trailing "?" —
        # but is unambiguously a question in this context ("X vs Y",
        # "difference between X and Y", "define X").
        "difference between", "differentiate between", "distinguish between",
        "compare and contrast", "advantages of", "disadvantages of",
        "pros and cons of", "define ", " vs ", " versus ",
        # Romanized Hindi/Hinglish
        "kya", "kaise", "kyun", "kyu", "kab", "kaun", "kahan", "kitna", "kitne",
        "batao", "bataiye", "samjhao", "samjhaiye",
        # Devanagari
        "क्या", "कैसे", "क्यों", "कब", "कौन", "कहाँ", "कितना", "कितने",
        "बताओ", "बताइए", "समझाओ", "समझाइए",
    ]
    return text_lower.endswith("?") or any(
        marker in text_lower for marker in question_markers
    )


def _has_speech(pcm_bytes: bytes) -> bool:
    """Return whether a PCM chunk has enough energy to contain speech."""
    if len(pcm_bytes) < BYTES_PER_SAMPLE:
        return False
    samples = array("h")
    samples.frombytes(pcm_bytes[: len(pcm_bytes) - len(pcm_bytes) % BYTES_PER_SAMPLE])
    if not samples:
        return False
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    return rms >= SPEECH_RMS_THRESHOLD


async def _generate_feedback(session_id: str):
    """Background task: generate post-session feedback report."""
    try:
        await asyncio.sleep(1)   # let final transcripts flush to DB
        from backend.feedback.service import FeedbackService
        async with AsyncSessionFactory() as db:
            svc = FeedbackService(db)
            await svc.generate_feedback(session_id)
            await db.commit()
        logger.info("Feedback generation complete: session=%s", session_id)
    except Exception as e:
        logger.exception("Feedback generation failed: session=%s error=%s", session_id, e)


async def _send(ws: WebSocket, data: dict):
    try:
        await ws.send_text(json.dumps(data))
    except Exception as e:
        logger.exception("WS send failed: type=%s error=%s", data.get("type"), e)
