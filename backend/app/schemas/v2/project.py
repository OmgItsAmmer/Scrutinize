"""Schemas for the multi-tenant project layer (ADR 001)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import Settings


class ProjectSettings(BaseModel):
    """Per-project pipeline overrides stored in projects.settings JSON.

    Any field left as None falls back to the global Settings value
    when resolved into a ProjectContext.
    """

    gate_model: str | None = None
    rewriter_model: str | None = None
    synthesis_model: str | None = None
    decision_model: str | None = None
    confidence_threshold: float | None = None
    max_attempts: int | None = None
    # Keyed by agent name: "gate", "synthesis".
    system_prompt_overrides: dict[str, str] = Field(default_factory=dict)


class ProjectContext(BaseModel):
    """Resolved runtime context injected into the pipeline per request.

    All fields are concrete values — fallback logic is applied once during
    resolution so agents remain stateless and simple.
    """

    project_id: UUID
    gate_model: str
    rewriter_model: str
    synthesis_model: str
    decision_model: str
    confidence_threshold: float
    max_attempts: int
    system_prompt_overrides: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_settings_and_overrides(
        cls,
        project_id: UUID,
        overrides: ProjectSettings,
        defaults: Settings,
    ) -> "ProjectContext":
        """Merge project-level overrides with global defaults."""
        return cls(
            project_id=project_id,
            gate_model=overrides.gate_model or defaults.local_llm_gate_model,
            rewriter_model=overrides.rewriter_model or defaults.local_llm_rewriter_model,
            synthesis_model=overrides.synthesis_model or defaults.local_llm_rewriter_model,
            decision_model=overrides.decision_model or defaults.local_llm_decision_model,
            confidence_threshold=(
                overrides.confidence_threshold
                if overrides.confidence_threshold is not None
                else defaults.v2_confidence_threshold
            ),
            max_attempts=(
                overrides.max_attempts
                if overrides.max_attempts is not None
                else defaults.v2_max_pipeline_attempts
            ),
            system_prompt_overrides=overrides.system_prompt_overrides,
        )


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Request body for POST /api/v2/projects."""

    name: str = Field(..., min_length=1, max_length=255)
    settings: dict[str, Any] = Field(default_factory=dict)


class CreateProjectResponse(BaseModel):
    """Response for POST /api/v2/projects — contains both keys."""

    project_id: UUID
    # Admin key: keep server-side only.
    api_key: str
    # Client key: safe to embed in frontend widgets.
    client_key: str


class ProjectInfoResponse(BaseModel):
    """Lightweight project info returned from GET /api/v2/projects/me."""

    project_id: UUID
    name: str
    settings: dict[str, Any]


class ProjectSignupRequest(BaseModel):
    """Request body for POST /v2/projects/signup."""

    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    settings: dict[str, Any] = Field(default_factory=dict)


class ProjectLoginRequest(BaseModel):
    """Request body for POST /v2/projects/login."""

    name: str = Field(...)
    password: str = Field(...)

