"""
OpenAI Whisper client for speech-to-text transcription.
Accepts raw PCM bytes at 16kHz/16bit/mono, converts to WAV, sends to API.
"""

import io
import wave
import logging

from openai import AsyncOpenAI
from backend.config import settings

logger = logging.getLogger(__name__)


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM in a WAV container (needed by Whisper API)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)       # mono
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buffer.getvalue()


class WhisperClient:

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_WHISPER_MODEL

    async def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> dict:
        """
        Transcribe PCM audio bytes.
        Returns {"text": str, "confidence": float, "language": str}
        """
        if len(pcm_bytes) < 1000:
            return {"text": "", "confidence": 0.0, "language": language}

        wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        try:
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
                response_format="verbose_json",
            )

            # verbose_json returns segments with individual confidence scores
            avg_confidence = 1.0
            if hasattr(response, "segments") and response.segments:
                confs = [
                    abs(seg.get("avg_logprob", 0))
                    for seg in response.segments
                    if "avg_logprob" in seg
                ]
                if confs:
                    # Convert log-prob to approximate confidence (heuristic)
                    avg_confidence = min(1.0, max(0.0, 1.0 - (sum(confs) / len(confs)) / 5))

            return {
                "text": response.text,
                "confidence": avg_confidence,
                "language": getattr(response, "language", language),
            }

        except Exception as e:
            logger.error("Whisper transcription error: %s", e)
            return {"text": "", "confidence": 0.0, "language": language}
