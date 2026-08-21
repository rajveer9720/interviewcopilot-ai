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
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_access_token
from backend.core.database import AsyncSessionFactory
from backend.core.redis import get_redis
from backend.sessions.service import SessionService
from backend.transcripts.whisper_client import WhisperClient
from backend.ai.router import LLMRouter
from backend.ai.prompt_builder import PromptBuilder

router = APIRouter()
logger = logging.getLogger(__name__)

whisper = WhisperClient()
llm_router = LLMRouter()
prompt_builder = PromptBuilder()


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
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info("WS connected: session=%s user=%s", session_id, user_id)

    # Notify client
    await _send(websocket, {
        "type": "connected",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    audio_buffer = bytearray()

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "audio_chunk":
                # Accumulate audio
                pcm_bytes = base64.b64decode(message["data"])
                audio_buffer.extend(pcm_bytes)

                # Process every ~1 second of audio (16kHz * 2 bytes * 1s = 32000 bytes)
                if len(audio_buffer) >= 32000:
                    chunk = bytes(audio_buffer)
                    audio_buffer.clear()

                    # Offload to async worker
                    asyncio.create_task(
                        _process_audio_chunk(websocket, session_id, user_id, chunk)
                    )

            elif msg_type == "session_end":
                await _send(websocket, {"type": "session_ending"})
                # Trigger background feedback generation
                asyncio.create_task(_generate_feedback(session_id))
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
):
    """
    1. Send to Whisper for transcription
    2. Detect if it's a question
    3. If question → build prompt → stream LLM response
    """
    try:
        # ── Step 1: Transcribe ─────────────────────────────
        result = await whisper.transcribe(audio_bytes)
        if not result or not result.get("text", "").strip():
            return

        text = result["text"].strip()
        confidence = result.get("confidence", 1.0)

        # Send partial transcript to client
        await _send(websocket, {
            "type": "transcript",
            "text": text,
            "is_final": True,
            "speaker": "user",
            "confidence": confidence,
        })

        # Save to DB
        async with AsyncSessionFactory() as db:
            svc = SessionService(db)
            is_question = _detect_question(text)
            transcript = await svc.save_transcript(
                session_id=session_id,
                content=text,
                confidence=confidence,
                is_question=is_question,
            )
            await db.commit()

        # ── Step 2: If question detected → LLM coaching ───
        if is_question:
            await _send(websocket, {
                "type": "question_detected",
                "text": text,
            })

            prompt = await prompt_builder.build(
                question=text,
                user_id=user_id,
            )

            full_response = ""
            async for token in await llm_router.route(prompt, user_id, stream=True):
                full_response += token
                await _send(websocket, {
                    "type": "ai_suggestion",
                    "token": token,
                })

            await _send(websocket, {
                "type": "ai_complete",
                "full_text": full_response,
            })

    except Exception as e:
        logger.error("Audio processing error: %s", e)
        await _send(websocket, {"type": "error", "message": "Processing error."})


def _detect_question(text: str) -> bool:
    """Heuristic question detection."""
    text_lower = text.lower().strip()
    question_starters = [
        "tell me", "describe", "explain", "what", "how", "why", "when",
        "can you", "could you", "would you", "have you", "do you",
        "walk me through", "give me an example",
    ]
    return text_lower.endswith("?") or any(
        text_lower.startswith(s) for s in question_starters
    )


async def _generate_feedback(session_id: str):
    """Background task: generate post-session feedback report."""
    await asyncio.sleep(1)   # let final transcripts flush to DB
    from backend.feedback.service import FeedbackService
    async with AsyncSessionFactory() as db:
        svc = FeedbackService(db)
        await svc.generate_feedback(session_id)
        await db.commit()


async def _send(ws: WebSocket, data: dict):
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass
