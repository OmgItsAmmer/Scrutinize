import tempfile
from pathlib import Path
from uuid import UUID

from app.core.config import Settings
from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus
from app.services.embedding_service import EmbeddingService
from app.services.ingestion import index_segments
from app.services.job_orchestrator import JobOrchestrator
from app.services.media_utils import probe_duration, resolve_media_source
from app.services.segment_windowing import window_transcript_segments
from app.services.transcription_service import TranscriptionService
from app.services.vector_store import VectorStore

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
AUDIO_STAGE = "audio_ingestion"


def is_audio_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in AUDIO_EXTENSIONS


class AudioProcessor:
    """Whisper transcription + segment embedding pipeline (M3)."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        transcription_service: TranscriptionService,
        settings: Settings,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._transcription_service = transcription_service
        self._settings = settings

    def process(self, job_id: UUID) -> int:
        job = self._orchestrator.get_job(job_id)
        if job is None:
            raise LookupError(f"Processing job {job_id} not found")

        file_record = self._orchestrator.get_file(job.file_id)
        if file_record is None:
            raise LookupError(f"File {job.file_id} not found")
        if file_record.modality != FileModality.AUDIO:
            raise ValueError(f"File {file_record.id} is not an audio file")

        self._orchestrator.update_job_status(job_id, JobStatus.RUNNING)
        self._orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

        temp_path: Path | None = None
        owns_temp_file = False
        try:
            suffix = Path(file_record.filename).suffix or ".mp3"
            temp_path = resolve_media_source(file_record.storage_path, suffix=suffix)
            owns_temp_file = file_record.storage_path.startswith(("http://", "https://"))

            duration = probe_duration(temp_path, settings=self._settings)
            file_record.duration_seconds = duration
            self._orchestrator.session.add(file_record)
            self._orchestrator.session.commit()
            self._orchestrator.session.refresh(file_record)

            transcript_segments = self._transcription_service.transcribe_file(temp_path)
            windows = window_transcript_segments(
                transcript_segments,
                min_seconds=self._settings.audio_segment_min_seconds,
                max_seconds=self._settings.audio_segment_max_seconds,
            )
            if not windows:
                raise ValueError("No transcript segments produced from audio")

            segment_count = index_segments(
                self._orchestrator,
                self._embedding_service,
                self._vector_store,
                file_record,
                windows,
                FileModality.AUDIO,
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
            if temp_path is not None and owns_temp_file:
                temp_path.unlink(missing_ok=True)
