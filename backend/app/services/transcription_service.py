from pathlib import Path

from openai import OpenAI

from app.core.config import Settings
from app.services.segment_windowing import TranscriptSegment


class TranscriptionService:
    """Whisper transcription with timestamped segments."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for transcription.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.whisper_model

    def transcribe_file(self, audio_path: Path) -> list[TranscriptSegment]:
        with audio_path.open("rb") as audio_file:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                response_format="verbose_json",
            )

        segments: list[TranscriptSegment] = []
        for segment in response.segments or []:
            text = segment.text.strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=text,
                )
            )
        return segments
