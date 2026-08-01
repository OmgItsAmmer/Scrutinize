import logging
from collections.abc import Callable
from uuid import UUID

from sqlmodel import Session

from app.models.conversation import ChatConversation, ChatMessage  # noqa: F401
from app.models.file import File  # noqa: F401
from app.models.pipeline_log import PipelineRun, PipelineStep  # noqa: F401
from app.models.processing_job import ProcessingJob  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.segment import Segment  # noqa: F401
from app.models.user import ProjectMember, User  # noqa: F401

from app.core.config import Settings, reload_settings
from app.core.database import get_engine
from app.services.audio_processor import AudioProcessor
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.qdrant_errors import describe_worker_error
from app.services.text_processor import TextProcessor
from app.services.transcription_service import TranscriptionService
from app.services.v2.llm_clients import CloudLlmClient
from app.services.v5.context_enricher import ContextEnricher
from app.services.vector_store import VectorStore
from app.services.video_processor import VideoProcessor
from app.services.vision_service import VisionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _format_task_error(exc: BaseException) -> str:
    return describe_worker_error(exc)


def _run_ingestion(job_id: str, task_name: str, run: Callable[[], int]) -> dict[str, str | int]:
    settings = reload_settings()
    logger.info(
        "%s starting job_id=%s qdrant_url=%s redis_url=%s",
        task_name,
        job_id,
        settings.qdrant_url,
        settings.redis_url,
    )
    try:
        segment_count = run()
    except Exception as exc:
        logger.exception(
            "%s FAILED job_id=%s error=%s",
            task_name,
            job_id,
            _format_task_error(exc),
        )
        raise
    logger.info("%s done job_id=%s segments=%d", task_name, job_id, segment_count)
    return {"job_id": job_id, "status": "done", "segments": segment_count}


def _build_services(settings: Settings):
    embedding_service = EmbeddingService(settings)
    vector_store = VectorStore(settings)
    transcription_service = TranscriptionService(settings)
    vision_service = VisionService(settings)
    return embedding_service, vector_store, transcription_service, vision_service


@celery_app.task(name="ping")
def ping() -> str:
    """Smoke task to verify Celery worker connectivity."""
    settings = reload_settings()
    logger.info("ping ok qdrant_url=%s", settings.qdrant_url)
    return "pong"


def _build_context_enricher(settings: Settings) -> ContextEnricher | None:
    if not settings.contextual_retrieval_enabled or not settings.openai_api_key.strip():
        return None
    return ContextEnricher(CloudLlmClient(settings), settings)


@celery_app.task(name="process_text", bind=True)
def process_text(self, job_id: str) -> dict[str, str | int]:
    """Run the text ingestion pipeline for a queued job."""

    def run() -> int:
        settings = reload_settings()
        embedding_service, vector_store, _, vision_service = _build_services(settings)
        context_enricher = _build_context_enricher(settings)
        with Session(get_engine()) as session:
            orchestrator = JobOrchestrator(session)
            processor = TextProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                settings,
                vision_service=vision_service,
                context_enricher=context_enricher,
            )
            return processor.process(UUID(job_id))

    return _run_ingestion(job_id, "process_text", run)


@celery_app.task(name="reindex_file", bind=True)
def reindex_file(self, file_id: str) -> dict[str, str | int]:
    """Re-parse, re-chunk, re-enrich and re-embed an existing text file (V5 M7).

    Atomically swaps vectors: the new segments/points are upserted under fresh
    IDs by TextProcessor.process() *before* the pre-reindex segments/points
    (captured up front) are deleted, so search never sees a gap.
    """
    settings = reload_settings()
    embedding_service, vector_store, _, vision_service = _build_services(settings)
    context_enricher = _build_context_enricher(settings)

    with Session(get_engine()) as session:
        orchestrator = JobOrchestrator(session)
        file_record = orchestrator.get_file(UUID(file_id))
        if file_record is None:
            raise LookupError(f"File {file_id} not found")
        if file_record.modality != file_record.modality.TEXT:
            raise ValueError(f"reindex_file only supports text files, got {file_record.modality}")

        stale_segments = orchestrator.list_segments_for_file(file_record.id)
        stale_segment_ids = [s.id for s in stale_segments]

        job = orchestrator.create_job(file_id=file_record.id, stage="reindex")
        processor = TextProcessor(
            orchestrator,
            embedding_service,
            vector_store,
            settings,
            vision_service=vision_service,
            context_enricher=context_enricher,
        )

        def run() -> int:
            return processor.process(job.id)

        result = _run_ingestion(str(job.id), "reindex_file", run)

        if stale_segment_ids:
            vector_store.delete_by_ids(stale_segment_ids)
            for segment in stale_segments:
                session.delete(segment)
            session.commit()

    return result


@celery_app.task(name="process_audio", bind=True)
def process_audio(self, job_id: str) -> dict[str, str | int]:
    """Run the audio ingestion pipeline for a queued job."""

    def run() -> int:
        settings = reload_settings()
        embedding_service, vector_store, transcription_service, _ = _build_services(settings)
        with Session(get_engine()) as session:
            orchestrator = JobOrchestrator(session)
            processor = AudioProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                transcription_service,
                settings,
            )
            return processor.process(UUID(job_id))

    return _run_ingestion(job_id, "process_audio", run)


@celery_app.task(name="process_video", bind=True)
def process_video(self, job_id: str) -> dict[str, str | int]:
    """Run the video ingestion pipeline for a queued job."""

    def run() -> int:
        settings = reload_settings()
        embedding_service, vector_store, transcription_service, vision_service = _build_services(
            settings
        )
        with Session(get_engine()) as session:
            orchestrator = JobOrchestrator(session)
            processor = VideoProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                transcription_service,
                vision_service,
                settings,
            )
            return processor.process(UUID(job_id))

    return _run_ingestion(job_id, "process_video", run)
