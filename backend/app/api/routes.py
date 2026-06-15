from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app import __version__
from app.core.config import Settings
from app.core.deps import get_app_settings, get_db_session, get_job_orchestrator
from app.schemas.health import HealthResponse
from app.schemas.job import JobStatusResponse
from app.services.health import build_health_response
from app.services.job_orchestrator import JobOrchestrator

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    return build_health_response(settings, session, version=__version__)


@router.get("/status/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
def get_job_status(
    job_id: UUID,
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
) -> JobStatusResponse:
    job = orchestrator.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse.model_validate(job)
