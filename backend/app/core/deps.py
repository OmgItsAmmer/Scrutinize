from collections.abc import Generator

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.vector_store import VectorStore


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_app_settings() -> Settings:
    return get_settings()


def get_job_orchestrator(session: Session = Depends(get_db_session)) -> JobOrchestrator:
    return JobOrchestrator(session)


def get_cloudinary_storage(settings: Settings = Depends(get_app_settings)) -> CloudinaryStorage:
    return CloudinaryStorage(settings)


def get_embedding_service(settings: Settings = Depends(get_app_settings)) -> EmbeddingService:
    return EmbeddingService(settings)


def get_vector_store(settings: Settings = Depends(get_app_settings)) -> VectorStore:
    return VectorStore(settings)
