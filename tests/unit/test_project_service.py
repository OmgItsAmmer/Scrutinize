"""Unit tests for ProjectService — key generation, lookup, and context resolution."""

import pytest
from uuid import UUID
from unittest.mock import MagicMock

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.project import Project
from app.schemas.v2.project import ProjectContext, ProjectSettings
from app.services.project_service import ProjectService, _SK_PREFIX, _PK_PREFIX


@pytest.fixture()
def db_session():
    """In-memory SQLite session with the full SQLModel metadata."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def project_service(db_session):
    return ProjectService(db_session)


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


class TestKeyGeneration:
    def test_admin_key_has_correct_prefix(self, project_service):
        project = project_service.create_project("test-app", {})
        assert project.api_key.startswith(_SK_PREFIX)

    def test_client_key_has_correct_prefix(self, project_service):
        project = project_service.create_project("test-app", {})
        assert project.client_key.startswith(_PK_PREFIX)

    def test_keys_are_unique_across_projects(self, project_service):
        p1 = project_service.create_project("app-alpha", {})
        p2 = project_service.create_project("app-beta", {})
        assert p1.api_key != p2.api_key
        assert p1.client_key != p2.client_key

    def test_keys_have_sufficient_length(self, project_service):
        project = project_service.create_project("test-app", {})
        # Prefix (len ~17) + 48 hex chars = 65+
        assert len(project.api_key) > 40
        assert len(project.client_key) > 40


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestProjectLookup:
    def test_get_by_admin_key_returns_project(self, project_service):
        created = project_service.create_project("myapp", {})
        found = project_service.get_by_admin_key(created.api_key)
        assert found is not None
        assert found.id == created.id

    def test_get_by_client_key_returns_project(self, project_service):
        created = project_service.create_project("myapp", {})
        found = project_service.get_by_client_key(created.client_key)
        assert found is not None
        assert found.id == created.id

    def test_get_by_invalid_key_returns_none(self, project_service):
        assert project_service.get_by_admin_key("scrutinize_sk_nonexistent") is None
        assert project_service.get_by_client_key("scrutinize_pk_nonexistent") is None


# ---------------------------------------------------------------------------
# Context resolution
# ---------------------------------------------------------------------------


class TestContextResolution:
    def test_context_uses_project_overrides(self, project_service):
        from app.core.config import Settings

        settings = Settings(
            DATABASE_URL="sqlite://",
            OPENAI_API_KEY="test",
            LOCAL_LLM_BASE_URL="http://local",
        )
        project = project_service.create_project(
            "custom-app",
            {
                "gate_model": "custom-gate-model",
                "synthesis_model": "custom-synthesis-model",
                "confidence_threshold": 0.95,
                "max_attempts": 3,
            },
        )
        ctx = project_service.resolve_context(project, settings)
        assert ctx.gate_model == "custom-gate-model"
        assert ctx.synthesis_model == "custom-synthesis-model"
        assert ctx.confidence_threshold == 0.95
        assert ctx.max_attempts == 3
        assert isinstance(ctx.project_id, UUID)

    def test_context_falls_back_to_global_defaults(self, project_service):
        from app.core.config import Settings

        settings = Settings(
            DATABASE_URL="sqlite://",
            OPENAI_API_KEY="test",
            LOCAL_LLM_BASE_URL="http://local",
            local_llm_gate_model="global-gate-model",
            v2_confidence_threshold=0.7,
            v2_max_pipeline_attempts=2,
        )
        project = project_service.create_project("bare-app", {})
        ctx = project_service.resolve_context(project, settings)
        assert ctx.gate_model == "global-gate-model"
        assert ctx.confidence_threshold == 0.7
        assert ctx.max_attempts == 2
