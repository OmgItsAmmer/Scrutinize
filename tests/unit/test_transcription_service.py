from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.transcription_service import TranscriptionService


@pytest.mark.unit
def test_transcription_service_maps_whisper_segments(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake-audio")

    settings = Settings(openai_api_key="test-key")
    service = TranscriptionService(settings)
    response = MagicMock()
    response.segments = [
        MagicMock(start=0.0, end=2.5, text=" Hello "),
        MagicMock(start=2.5, end=5.0, text=""),
    ]

    with patch.object(service._client.audio.transcriptions, "create", return_value=response):
        segments = service.transcribe_file(audio_path)

    assert len(segments) == 1
    assert segments[0].text == "Hello"
    assert segments[0].start == 0.0
