from uuid import UUID

from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.services.audio_processor import AudioProcessor
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.text_processor import TextProcessor
from app.services.transcription_service import TranscriptionService
from app.services.vector_store import VectorStore
from app.services.video_processor import VideoProcessor
from app.services.vision_service import VisionService
from app.workers.celery_app import celery_app


def _build_services(settings):
    embedding_service = EmbeddingService(settings)
    vector_store = VectorStore(settings)
    transcription_service = TranscriptionService(settings)
    vision_service = VisionService(settings)
    return embedding_service, vector_store, transcription_service, vision_service


@celery_app.task(name="ping")
def ping() -> str:
    """Smoke task to verify Celery worker connectivity."""
    return "pong"


@celery_app.task(name="process_text", bind=True)
def process_text(self, job_id: str) -> dict[str, str | int]:
    """Run the text ingestion pipeline for a queued job."""
    settings = get_settings()
    embedding_service, vector_store, _, _ = _build_services(settings)
    with Session(get_engine()) as session:
        orchestrator = JobOrchestrator(session)
        processor = TextProcessor(
            orchestrator,
            embedding_service,
            vector_store,
            settings,
        )
        segment_count = processor.process(UUID(job_id))
    return {"job_id": job_id, "status": "done", "segments": segment_count}


@celery_app.task(name="process_audio", bind=True)
def process_audio(self, job_id: str) -> dict[str, str | int]:
    """Run the audio ingestion pipeline for a queued job."""
    settings = get_settings()
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
        segment_count = processor.process(UUID(job_id))
    return {"job_id": job_id, "status": "done", "segments": segment_count}


@celery_app.task(name="process_video", bind=True)
def process_video(self, job_id: str) -> dict[str, str | int]:
    """Run the video ingestion pipeline for a queued job."""
    settings = get_settings()
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
        segment_count = processor.process(UUID(job_id))
    return {"job_id": job_id, "status": "done", "segments": segment_count}
