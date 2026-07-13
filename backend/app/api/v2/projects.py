"""Project management endpoints (multi-tenant registration and info)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_current_user,
    get_db_session,
    get_project_from_admin_key,
)
from app.models.project import Project
from app.models.user import ProjectMember, User
from app.schemas.v2.project import (
    ChangePasswordRequest,
    CreateProjectRequest,
    CreateProjectResponse,
    PasswordUpdatedResponse,
    ProjectContext,
    ProjectInfoResponse,
    ProjectLoginRequest,
    ProjectSettings,
    ProjectSignupRequest,
    ResetPasswordRequest,
    UserCreateProjectRequest,
    UserProjectListResponse,
    UserProjectResponse,
)
from app.services.project_service import ProjectService

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
        UserProjectResponse(project_id=project.id, name=project.name, role=member.role, client_key=project.client_key, created_at=project.created_at.isoformat())
        for project, member in rows
    ])


@router.post("/mine", response_model=UserProjectResponse, status_code=201)
def create_user_project(
    body: UserCreateProjectRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserProjectResponse:
    project = ProjectService(session).create_project(body.name.strip(), body.settings, allow_duplicate_name=True)
    member = ProjectMember(user_id=user.id, project_id=project.id, role="owner")
    session.add(member)
    session.commit()
    return UserProjectResponse(project_id=project.id, name=project.name, role=member.role, client_key=project.client_key, created_at=project.created_at.isoformat())


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


@router.post("/me/password", response_model=PasswordUpdatedResponse)
def change_project_password(
    body: ChangePasswordRequest,
    project_ctx: ProjectContext = Depends(get_project_from_admin_key),
    session: Session = Depends(get_db_session),
) -> PasswordUpdatedResponse:
    """Change or reset the project login password (admin API key required).

    - Provide **current_password** + **new_password** to change while knowing the old password.
    - Omit **current_password** to reset using only your admin API key (e.g. still logged in).
    """
    svc = ProjectService(session)
    updated = svc.change_password(
        project_ctx.project_id,
        body.new_password,
        current_password=body.current_password,
    )
    if not updated:
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    return PasswordUpdatedResponse()


@router.post("/reset-password", response_model=PasswordUpdatedResponse)
def reset_project_password(
    body: ResetPasswordRequest,
    session: Session = Depends(get_db_session),
) -> PasswordUpdatedResponse:
    """Reset password when logged out — requires project name and admin API key."""
    svc = ProjectService(session)
    updated = svc.reset_password_with_admin_key(body.name, body.api_key, body.new_password)
    if not updated:
        raise HTTPException(
            status_code=401,
            detail="Invalid project name or admin API key.",
        )
    return PasswordUpdatedResponse()



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
        settings=project.settings,
    )

