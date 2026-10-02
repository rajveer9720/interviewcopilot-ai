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

# Candidates using this app only ever speak English or Hindi/Hinglish (see
# ws_handler.py's question markers). Any other detected language is Whisper
# hallucinating on noise (fan hum, room echo) rather than real speech — it
# defaults to random-language YouTube-caption filler when it can't make out
# words, not just English ones.
ALLOWED_LANGUAGES = {"en", "hi"}

# The most common stock phrases Whisper hallucinates on silence/noise,
# trained into it from YouTube captions. Matched as a whole normalized
# utterance (not a substring) so a real sentence that happens to contain
# "thank you" mid-sentence — e.g. "Thank you for asking, let me explain" —
# is never touched; this only catches these phrases standing alone.
KNOWN_HALLUCINATION_PHRASES = {
    "you",
    "thank you",
    "thank you.",
    "thanks",
    "that's it",
    "the end",
    "bye",
    "bye bye",
    "we made it, so please",
    "captions for this",
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "don't forget to subscribe",
    "like and subscribe",
    "subscribe to my channel",
    "see you in the next video",
    "see you next time",
    "captions by",
    "subtitles by",
}


def _is_known_hallucination_phrase(text: str) -> bool:
    normalized = text.strip().strip(".!?").lower()
    return normalized in KNOWN_HALLUCINATION_PHRASES


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
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=20, max_retries=1)
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

            detected_language = getattr(response, "language", None)
            if detected_language:
                detected_language = {"english": "en", "hindi": "hi"}.get(
                    detected_language.lower(), detected_language.lower())

            if _is_hallucinated_silence(segments):
                logger.info(
                    "Whisper discarded likely hallucination on silence/noise: text=%r",
                    response.text,
                )
                return {"text": "", "confidence": 0.0, "language": language or "auto"}

            if detected_language and detected_language not in ALLOWED_LANGUAGES:
                logger.info(
                    "Whisper discarded unexpected-language hallucination: language=%s text=%r",
                    detected_language,
                    response.text,
                )
                return {"text": "", "confidence": 0.0, "language": language or "auto"}

            if _is_known_hallucination_phrase(response.text or ""):
                logger.info(
                    "Whisper discarded known hallucination phrase: text=%r",
                    response.text,
                )
                return {"text": "", "confidence": 0.0, "language": language or "auto"}

            result = {
                "text": response.text,
                "confidence": avg_confidence,
                "language": detected_language or language,
            }
            logger.info(
                "Whisper API response: chars=%d language=%s",
                len(result["text"] or ""),
                result["language"],
            )
            return result

        except Exception as e:
            logger.exception("Whisper transcription error: %s", e)
            raise RuntimeError("Transcription unavailable") from e
