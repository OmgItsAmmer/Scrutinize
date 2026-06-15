from collections.abc import Generator

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.job_orchestrator import JobOrchestrator


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_app_settings() -> Settings:
    return get_settings()


def get_job_orchestrator(session: Session = Depends(get_db_session)) -> JobOrchestrator:
    return JobOrchestrator(session)


def get_cloudinary_storage(settings: Settings = Depends(get_app_settings)) -> CloudinaryStorage:
    return CloudinaryStorage(settings)
