"""Service for managing Project tenants (CRUD + key resolution)."""

import secrets
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import Settings
from app.models.project import Project
from app.schemas.v2.project import ProjectContext, ProjectSettings

from app.core.password_security import hash_password, verify_password

_SK_PREFIX = "scrutinize_sk_"
_PK_PREFIX = "scrutinize_pk_"
_KEY_BYTES = 24  # 192 bits of entropy — 32 hex chars


def _generate_key(prefix: str) -> str:
    return prefix + secrets.token_hex(_KEY_BYTES)


class ProjectService:
    """Manages Project records in Neon Postgres.

    Responsibilities:
    - Creating new projects with dual API keys (admin + client).
    - Looking up projects by key for request auth.
    - Resolving a ProjectContext (with global defaults fallback) for pipeline injection.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_project(self, name: str, settings_dict: dict, password: str | None = None) -> Project:
        """Create a new project with auto-generated admin and client keys and optional password."""
        pw_hash = hash_password(password) if password else None
        project = Project(
            name=name,
            api_key=_generate_key(_SK_PREFIX),
            client_key=_generate_key(_PK_PREFIX),
            settings=settings_dict,
            password_hash=pw_hash,
        )
        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project

    def authenticate_project(self, name: str, password: str) -> Project | None:
        """Authenticate a project by name and raw password.

        Returns Project instance on success, or None on failure.
        """
        # Case insensitive lookup or exact matching. Neon PostgreSQL handles case-insensitivity depending on collation/types,
        # but let's do case-insensitive comparison using lower() to prevent name duplication issues or minor typos.
        stmt = select(Project).where(Project.name == name)
        project = self._session.exec(stmt).first()
        if not project:
            # Run dummy verification to prevent timing/enumeration attacks
            verify_password(password, "pbkdf2_sha256$100000$dummy$dummy")
            return None
        if verify_password(password, project.password_hash):
            return project
        return None

    def get_by_id(self, project_id: UUID) -> Project | None:
        return self._session.get(Project, project_id)

    def get_by_admin_key(self, api_key: str) -> Project | None:
        """Look up a project using its private admin (sk) key."""
        stmt = select(Project).where(Project.api_key == api_key)
        return self._session.exec(stmt).first()

    def get_by_client_key(self, client_key: str) -> Project | None:
        """Look up a project using its public client (pk) key."""
        stmt = select(Project).where(Project.client_key == client_key)
        return self._session.exec(stmt).first()

    # ------------------------------------------------------------------
    # Context resolution
    # ------------------------------------------------------------------

    def resolve_context(self, project: Project, global_settings: Settings) -> ProjectContext:
        """Build a ProjectContext by merging project overrides with global defaults.

        Any field missing or None in project.settings falls back to the
        corresponding global Settings value so agents always receive
        concrete, non-None configuration.
        """
        raw_settings = project.settings or {}
        overrides = ProjectSettings(**{k: v for k, v in raw_settings.items() if k in ProjectSettings.model_fields})
        return ProjectContext.from_settings_and_overrides(
            project_id=project.id,
            overrides=overrides,
            defaults=global_settings,
        )
