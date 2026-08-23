"""
Characterization tests for `_is_hallucinated_silence` (this session's fix to
backend/transcripts/whisper_client.py). Pins today's thresholds before Phase
3 adds retry logic around the same call site.
"""

from backend.transcripts.whisper_client import (
    ALLOWED_LANGUAGES,
    _is_hallucinated_silence,
    _is_known_hallucination_phrase,
)


def _segment(no_speech_prob=0.0, avg_logprob=0.0, compression_ratio=1.0) -> dict:
    return {
        "no_speech_prob": no_speech_prob,
        "avg_logprob": avg_logprob,
        "compression_ratio": compression_ratio,
    }


def test_no_segments_is_not_hallucination():
    assert _is_hallucinated_silence([]) is False


def test_confident_real_speech_is_not_hallucination():
    segments = [_segment(no_speech_prob=0.05, avg_logprob=-0.3, compression_ratio=1.5)]
    assert _is_hallucinated_silence(segments) is False


def test_silent_low_confidence_audio_is_hallucination():
    segments = [_segment(no_speech_prob=0.9, avg_logprob=-1.5, compression_ratio=1.0)]
    assert _is_hallucinated_silence(segments) is True


def test_repetitive_text_on_quiet_audio_is_hallucination_via_compression():
    # "you you you you" — plausible words individually, but no_speech_prob is
    # elevated and the repetition drives compression_ratio up even though
    # avg_logprob alone isn't damning.
    segments = [_segment(no_speech_prob=0.7, avg_logprob=-0.5, compression_ratio=3.0)]
    assert _is_hallucinated_silence(segments) is True


def test_elevated_no_speech_alone_is_not_enough():
    segments = [_segment(no_speech_prob=0.8, avg_logprob=-0.2, compression_ratio=1.2)]
    assert _is_hallucinated_silence(segments) is False


def test_low_confidence_alone_is_not_enough_without_no_speech_signal():
    segments = [_segment(no_speech_prob=0.3, avg_logprob=-2.0, compression_ratio=1.0)]
    assert _is_hallucinated_silence(segments) is False


def test_exact_hallucination_phrases_are_flagged():
    for text in [
        "you", "You.", "Thank you.", "thank you", "That's it", "the end",
        "Captions for this", "We made it, so please",
        "Thank you for watching", "Please subscribe",
        "Don't forget to subscribe", "See you next time",
    ]:
        assert _is_known_hallucination_phrase(text) is True


def test_real_sentence_containing_thank_you_is_not_flagged():
    assert _is_known_hallucination_phrase("Thank you for asking, let me explain my approach") is False


def test_real_answer_is_not_flagged():
    assert _is_known_hallucination_phrase("A closure lets a function remember its lexical scope") is False


def test_allowed_languages_are_english_and_hindi():
    assert ALLOWED_LANGUAGES == {"en", "hi"}
