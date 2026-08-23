"""
Characterization tests for `_detect_question` (backend/sessions/ws_handler.py).

These pin TODAY's behavior before Phase 5 replaces this with a hybrid
keyword+LLM detector, so a regression in the keyword fast-path shows up as a
failing test instead of a silent behavior change.
"""

import pytest

from backend.sessions.ws_handler import _detect_question


@pytest.mark.parametrize(
    "text",
    [
        "What is NestJS?",
        "lexical scope?",
        "difference between deep copy vs shallow copy?",
        "difference between deep copy and shallow copy",
        "deep copy vs shallow copy",
        "define lexical scope",
        "Can you explain lexical scope",
        "Achha ye batao, dependency injection kya hota hai",
        "क्या आप बता सकते हैं",
        "walk me through your last project",
    ],
)
def test_detects_question(text):
    assert _detect_question(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "you",
        "Thank you for watching.",
        "okay next question",
        "so that went well, thanks",
        "lexical scope",  # bare topic name, no verb/marker/"?" — known limitation
        "",
    ],
)
def test_does_not_detect_question(text):
    assert _detect_question(text) is False
