import logging
from collections.abc import Callable
from uuid import UUID

from sqlmodel import Session

from app.core.config import Settings, reload_settings
from app.core.database import get_engine
from app.services.audio_processor import AudioProcessor
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.qdrant_errors import describe_worker_error
from app.services.text_processor import TextProcessor
from app.services.transcription_service import TranscriptionService
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


@celery_app.task(name="process_text", bind=True)
def process_text(self, job_id: str) -> dict[str, str | int]:
    """Run the text ingestion pipeline for a queued job."""

    def run() -> int:
        settings = reload_settings()
        embedding_service, vector_store, _, vision_service = _build_services(settings)
        with Session(get_engine()) as session:
            orchestrator = JobOrchestrator(session)
            processor = TextProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                settings,
                vision_service=vision_service,
            )
            return processor.process(UUID(job_id))

    return _run_ingestion(job_id, "process_text", run)


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
