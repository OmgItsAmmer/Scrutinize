from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus
from app.services.audio_processor import AudioProcessor
from app.services.job_orchestrator import JobOrchestrator
from app.services.segment_windowing import TranscriptSegment


@pytest.mark.unit
def test_audio_processor_indexes_transcript_windows(session):
    settings = Settings(openai_api_key="test-key")
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="clip.mp3",
        modality=FileModality.AUDIO,
        storage_path="https://example.com/clip.mp3",
        size_bytes=1000,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="audio_ingestion")

    embedding_service = MagicMock()
    embedding_service.embed_texts.return_value = [[0.1, 0.2]]
    vector_store = MagicMock()
    transcription_service = MagicMock()
    transcription_service.transcribe_file.return_value = [
        TranscriptSegment(start=0.0, end=20.0, text="Hello audio")
    ]

    processor = AudioProcessor(
        orchestrator,
        embedding_service,
        vector_store,
        transcription_service,
        settings,
    )

    with (
        patch(
            "app.services.audio_processor.resolve_media_source",
            return_value=Path("fake.mp3"),
        ),
        patch("app.services.audio_processor.probe_duration", return_value=20.0),
        patch.object(Path, "unlink", return_value=None),
        patch(
            "app.services.audio_processor.index_segments",
            return_value=1,
        ) as index_segments,
    ):
        count = processor.process(job.id)

    assert count == 1
    index_segments.assert_called_once()
    updated_job = orchestrator.get_job(job.id)
    assert updated_job is not None
    assert updated_job.status == JobStatus.DONE
    updated_file = orchestrator.get_file(file_record.id)
    assert updated_file is not None
    assert updated_file.status == FileStatus.INDEXED
    assert updated_file.duration_seconds == 20.0
