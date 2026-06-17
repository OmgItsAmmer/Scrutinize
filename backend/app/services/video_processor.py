import tempfile
from pathlib import Path
from uuid import UUID

from app.core.config import Settings
from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus
from app.services.embedding_service import EmbeddingService
from app.services.ingestion import index_segments
from app.services.job_orchestrator import JobOrchestrator
from app.services.media_utils import (
    extract_audio,
    extract_keyframes,
    probe_duration,
    resolve_media_source,
)
from app.services.segment_windowing import (
    KeyframeCaption,
    merge_transcript_with_captions,
    window_transcript_segments,
)
from app.services.transcription_service import TranscriptionService
from app.services.vector_store import VectorStore
from app.services.vision_service import VisionService

VIDEO_EXTENSIONS = {".mp4", ".mov"}
VIDEO_STAGE = "video_ingestion"


def is_video_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


class VideoProcessor:
    """FFmpeg + Whisper + vision captioning pipeline (M4)."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        transcription_service: TranscriptionService,
        vision_service: VisionService,
        settings: Settings,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._transcription_service = transcription_service
        self._vision_service = vision_service
        self._settings = settings

    def process(self, job_id: UUID) -> int:
        job = self._orchestrator.get_job(job_id)
        if job is None:
            raise LookupError(f"Processing job {job_id} not found")

        file_record = self._orchestrator.get_file(job.file_id)
        if file_record is None:
            raise LookupError(f"File {job.file_id} not found")
        if file_record.modality != FileModality.VIDEO:
            raise ValueError(f"File {file_record.id} is not a video file")

        self._orchestrator.update_job_status(job_id, JobStatus.RUNNING)
        self._orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

        temp_video: Path | None = None
        owns_temp_file = False
        try:
            suffix = Path(file_record.filename).suffix or ".mp4"
            temp_video = resolve_media_source(file_record.storage_path, suffix=suffix)
            owns_temp_file = file_record.storage_path.startswith(("http://", "https://"))

            duration = probe_duration(temp_video, settings=self._settings)
            file_record.duration_seconds = duration
            self._orchestrator.session.add(file_record)
            self._orchestrator.session.commit()
            self._orchestrator.session.refresh(file_record)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                audio_path = temp_dir_path / "audio.wav"
                extract_audio(temp_video, audio_path, settings=self._settings)

                transcript_segments = self._transcription_service.transcribe_file(audio_path)
                transcript_windows = window_transcript_segments(
                    transcript_segments,
                    min_seconds=self._settings.audio_segment_min_seconds,
                    max_seconds=self._settings.audio_segment_max_seconds,
                )

                keyframe_items = extract_keyframes(
                    temp_video,
                    temp_dir_path / "frames",
                    settings=self._settings,
                )
                frame_paths = [frame_path for frame_path, _ in keyframe_items]
                frame_captions = self._vision_service.caption_images(frame_paths)
                captions = [
                    KeyframeCaption(timestamp=timestamp, caption=caption)
                    for (_, timestamp), caption in zip(keyframe_items, frame_captions, strict=True)
                ]

                merged_windows = merge_transcript_with_captions(transcript_windows, captions)
                if not merged_windows:
                    raise ValueError("No video segments produced from transcript or captions")

                segment_count = index_segments(
                    self._orchestrator,
                    self._embedding_service,
                    self._vector_store,
                    file_record,
                    merged_windows,
                    FileModality.VIDEO,
                )

            self._orchestrator.update_job_status(job_id, JobStatus.DONE)
            self._orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)
            return segment_count
        except Exception as exc:
            self._orchestrator.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=str(exc),
            )
            self._orchestrator.mark_file_status(file_record.id, FileStatus.FAILED)
            raise
        finally:
            if temp_video is not None and owns_temp_file:
                temp_video.unlink(missing_ok=True)
