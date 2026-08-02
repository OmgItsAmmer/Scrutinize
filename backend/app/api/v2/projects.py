"""Project management endpoints (multi-tenant registration and info)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_cloudinary_storage,
    get_current_user,
    get_db_session,
    get_job_orchestrator,
    get_project_from_admin_key,
    get_vector_store,
)
from app.models.project import Project
from app.models.user import ProjectMember, User
from app.schemas.v2.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectContext,
    ProjectInfoResponse,
    ProjectLoginRequest,
    ProjectSettings,
    ProjectSignupRequest,
    UserCreateProjectRequest,
    UserProjectListResponse,
    UserProjectResponse,
)
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.job_orchestrator import JobOrchestrator
from app.services.project_deletion import ProjectDeletionService
from app.services.project_service import ProjectService
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=UserProjectListResponse)
def list_user_projects(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserProjectListResponse:
    rows = session.exec(
        select(Project, ProjectMember)
        .join(ProjectMember, Project.id == ProjectMember.project_id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
    ).all()
    return UserProjectListResponse(projects=[
        UserProjectResponse(
            project_id=project.id,
            name=project.name,
            role=member.role,
            client_key=project.client_key,
            created_at=project.created_at.isoformat(),
            api_key=project.api_key,
            settings=project.settings
        )
        for project, member in rows
    ])


@router.post("/mine", response_model=UserProjectResponse, status_code=201)
def create_user_project(
    body: UserCreateProjectRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> UserProjectResponse:
    from app.services.v2.prompt_generator import DEFAULT_SVG, generate_project_prompts
    prompts = generate_project_prompts(
        name=body.name.strip(),
        description=body.description.strip(),
        settings=settings,
    )

    project_settings = body.settings or {}
    project_settings["description"] = body.description.strip()
    project_settings["visual_svg"] = prompts.get("visual_svg") or DEFAULT_SVG
    project_settings["system_prompt_overrides"] = {
        "gate": prompts["gate"],
        "rewriter": prompts["rewriter"],
        "generic": prompts["generic"],
        "synthesis": prompts["synthesis"],
        "decision": prompts["decision"]
    }
    
    project = ProjectService(session).create_project(body.name.strip(), project_settings, allow_duplicate_name=True)
    member = ProjectMember(user_id=user.id, project_id=project.id, role="owner")
    session.add(member)
    session.commit()
    return UserProjectResponse(
        project_id=project.id,
        name=project.name,
        role=member.role,
        client_key=project.client_key,
        created_at=project.created_at.isoformat(),
        api_key=project.api_key,
        settings=project.settings
    )


@router.delete("/{project_id}", status_code=204)
def delete_user_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
    storage: CloudinaryStorage = Depends(get_cloudinary_storage),
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_app_settings),
) -> None:
    ProjectDeletionService(session, orchestrator, storage, vector_store, settings).delete_for_user(
        user, project_id
    )


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


@router.post("/me/password")
def change_project_password() -> None:
    """Project password changes are disabled."""
    raise HTTPException(status_code=410, detail="Project password changes are disabled.")


@router.post("/reset-password")
def reset_project_password() -> None:
    """Project password resets are disabled."""
    raise HTTPException(status_code=410, detail="Project password resets are disabled.")



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
        api_key=project.api_key,
        client_key=project.client_key,
        settings=project.settings,
    )


@router.patch("/me", response_model=ProjectInfoResponse)
def update_project_settings(
    body: ProjectSettings,
    project_ctx: ProjectContext = Depends(get_project_from_admin_key),
    session: Session = Depends(get_db_session),
) -> ProjectInfoResponse:
    """Update settings (models, thresholds, and system prompt overrides) for the authenticated project."""
    svc = ProjectService(session)
    project = svc.get_by_id(project_ctx.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    current_settings = project.settings or {}
    body_dict = body.model_dump(exclude_unset=True)
    if "system_prompt_overrides" in body_dict:
        existing_overrides = current_settings.get("system_prompt_overrides", {})
        existing_overrides.update(body_dict["system_prompt_overrides"])
        body_dict["system_prompt_overrides"] = existing_overrides

    current_settings.update(body_dict)
    project.settings = current_settings
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(project, "settings")

    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectInfoResponse(
        project_id=project.id,
        name=project.name,
        api_key=project.api_key,
        client_key=project.client_key,
        settings=project.settings,
    )

