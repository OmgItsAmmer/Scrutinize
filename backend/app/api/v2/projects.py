"""Project management endpoints (multi-tenant registration and info)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.config import Settings
from app.core.deps import get_app_settings, get_db_session, get_project_from_admin_key
from app.schemas.v2.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectContext,
    ProjectInfoResponse,
    ProjectSignupRequest,
    ProjectLoginRequest,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=CreateProjectResponse, status_code=201)
def register_project(
    body: CreateProjectRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> CreateProjectResponse:
    """Register a new project and receive admin + client API keys.

    - **api_key** (`scrutinize_sk_...`) — Private. Use only on your backend for uploads.
    - **client_key** (`scrutinize_pk_...`) — Public. Safe to embed in frontend widgets.
    """
    svc = ProjectService(session)
    try:
        project = svc.create_project(body.name, body.settings)
    except Exception as exc:
        # Unique constraint on name will surface here.
        raise HTTPException(status_code=409, detail=f"Project name already exists: {exc}") from exc
    return CreateProjectResponse(
        project_id=project.id,
        api_key=project.api_key,
        client_key=project.client_key,
    )


@router.post("/signup", response_model=CreateProjectResponse, status_code=201)
def signup_project(
    body: ProjectSignupRequest,
    session: Session = Depends(get_db_session),
) -> CreateProjectResponse:
    """Create a new project using secure password hashing."""
    svc = ProjectService(session)
    try:
        project = svc.create_project(body.name, body.settings, password=body.password)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Project name already exists.") from exc
    return CreateProjectResponse(
        project_id=project.id,
        api_key=project.api_key,
        client_key=project.client_key,
    )


@router.post("/login", response_model=CreateProjectResponse)
def login_project(
    body: ProjectLoginRequest,
    session: Session = Depends(get_db_session),
) -> CreateProjectResponse:
    """Authenticate a project name and password, returning active API keys."""
    svc = ProjectService(session)
    project = svc.authenticate_project(body.name, body.password)
    if not project:
        raise HTTPException(status_code=401, detail="Invalid project name or password.")
    return CreateProjectResponse(
        project_id=project.id,
        api_key=project.api_key,
        client_key=project.client_key,
    )



@router.get("/me", response_model=ProjectInfoResponse)
def get_project_info(
    project_ctx: ProjectContext = Depends(get_project_from_admin_key),
    session: Session = Depends(get_db_session),
) -> ProjectInfoResponse:
    """Return project info for the supplied admin API key."""
    svc = ProjectService(session)
    project = svc.get_by_id(project_ctx.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectInfoResponse(
        project_id=project.id,
        name=project.name,
        settings=project.settings,
    )
