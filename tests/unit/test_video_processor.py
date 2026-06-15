from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.services.job_orchestrator import JobOrchestrator
from app.services.segment_windowing import KeyframeCaption, TranscriptSegment
from app.services.video_processor import VideoProcessor


@pytest.mark.unit
def test_video_processor_merges_transcript_and_captions(session):
    settings = Settings(openai_api_key="test-key", video_max_keyframes=2)
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="clip.mp4",
        modality=FileModality.VIDEO,
        storage_path="https://example.com/clip.mp4",
        size_bytes=5000,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="video_ingestion")

    embedding_service = MagicMock()
    vector_store = MagicMock()
    transcription_service = MagicMock()
    transcription_service.transcribe_file.return_value = [
        TranscriptSegment(start=0.0, end=18.0, text="Hello video")
    ]
    vision_service = MagicMock()
    vision_service.caption_image.side_effect = ["Person waving", "Room interior"]

    processor = VideoProcessor(
        orchestrator,
        embedding_service,
        vector_store,
        transcription_service,
        vision_service,
        settings,
    )

    fake_frames = [(Path("frame1.jpg"), 0.0), (Path("frame2.jpg"), 5.0)]

    with (
        patch(
            "app.services.video_processor.resolve_media_source",
            return_value=Path("fake.mp4"),
        ),
        patch("app.services.video_processor.probe_duration", return_value=18.0),
        patch.object(Path, "unlink", return_value=None),
        patch("app.services.video_processor.extract_audio"),
        patch("app.services.video_processor.extract_keyframes", return_value=fake_frames),
        patch(
            "app.services.video_processor.index_segments",
            return_value=1,
        ) as index_segments,
    ):
        count = processor.process(job.id)

    assert count == 1
    assert vision_service.caption_image.call_count == 2
    index_segments.assert_called_once()
