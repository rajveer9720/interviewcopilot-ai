from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.transcripts.whisper_client import WhisperClient


@pytest.mark.parametrize("language, expected", [("english", "en"), ("hindi", "hi")])
async def test_full_language_names_are_not_discarded_as_noise(language, expected):
    client = WhisperClient()
    client.client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(
        text="What is a queue?", language=language, segments=[]))
    try:
        result = await client.transcribe(b"\x00\x01" * 1000)
        assert result["text"] == "What is a queue?"
        assert result["language"] == expected
    finally:
        await client.client.close()
