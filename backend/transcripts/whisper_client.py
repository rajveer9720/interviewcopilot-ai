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


def _seg_get(seg, key: str, default=0.0):
    """Segment items can come back as dicts or SDK model objects depending
    on the openai-python version — read either shape the same way."""
    return seg.get(key, default) if isinstance(seg, dict) else getattr(seg, key, default)


def _is_hallucinated_silence(segments) -> bool:
    """
    Whisper doesn't return "nothing" for silence/faint noise — it hallucinates
    fluent-sounding filler ("you", "Thank you for watching.") because it was
    trained on YouTube captions. Its own per-segment stats give this away:
    high no_speech_prob (it thought there was no speech here), very negative
    avg_logprob (it wasn't confident about the words it emitted anyway), or a
    high compression_ratio (the text is degenerately repetitive, e.g. "you
    you you you"). This is the same heuristic whisper.cpp/faster-whisper use
    to suppress hallucinated segments.
    """
    if not segments:
        return False
    no_speech = [_seg_get(s, "no_speech_prob", 0.0) for s in segments]
    logprob = [_seg_get(s, "avg_logprob", 0.0) for s in segments]
    compression = [_seg_get(s, "compression_ratio", 0.0) for s in segments]
    avg_no_speech = sum(no_speech) / len(no_speech)
    avg_logprob = sum(logprob) / len(logprob)
    max_compression = max(compression) if compression else 0.0
    return avg_no_speech > 0.6 and (avg_logprob < -1.0 or max_compression > 2.4)


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
        language: str | None = None,
    ) -> dict:
        """
        Transcribe PCM audio bytes.
        `language` is omitted by default so Whisper auto-detects it — callers
        speak a mix of Hindi and English, and forcing "en" made it mangle or
        mistranslate Hindi/Hinglish speech instead of transcribing it.
        Returns {"text": str, "confidence": float, "language": str}
        """
        if len(pcm_bytes) < 1000:
            logger.warning("Whisper skipped audio shorter than 1000 bytes: bytes=%d", len(pcm_bytes))
            return {"text": "", "confidence": 0.0, "language": language or "auto"}

        wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        try:
            logger.info(
                "Whisper API request: model=%s pcm_bytes=%d wav_bytes=%d language=%s",
                self.model,
                len(pcm_bytes),
                len(wav_bytes),
                language or "auto",
            )
            kwargs = dict(
                model=self.model,
                file=audio_file,
                response_format="verbose_json",
            )
            if language:
                kwargs["language"] = language
            response = await self.client.audio.transcriptions.create(**kwargs)

            # verbose_json returns segments with individual confidence scores
            segments = getattr(response, "segments", None) or []
            avg_confidence = 1.0
            if segments:
                confs = [abs(_seg_get(seg, "avg_logprob", 0.0)) for seg in segments]
                if confs:
                    # Convert log-prob to approximate confidence (heuristic)
                    avg_confidence = min(1.0, max(0.0, 1.0 - (sum(confs) / len(confs)) / 5))

            if _is_hallucinated_silence(segments):
                logger.info(
                    "Whisper discarded likely hallucination on silence/noise: "
                    "session_text=%r",
                    response.text,
                )
                return {"text": "", "confidence": 0.0, "language": language or "auto"}

            result = {
                "text": response.text,
                "confidence": avg_confidence,
                "language": getattr(response, "language", language),
            }
            logger.info(
                "Whisper API response: chars=%d language=%s",
                len(result["text"] or ""),
                result["language"],
            )
            return result

        except Exception as e:
            logger.exception("Whisper transcription error: %s", e)
            return {"text": "", "confidence": 0.0, "language": language}
