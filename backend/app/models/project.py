from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """Represents an external application integrated with the Scrutinize pipeline."""

    __tablename__ = "projects"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)

    # Admin (secret) key — scrutinize_sk_... — used for upload/management operations.
    # Never expose to frontend clients.
    api_key: str = Field(unique=True, index=True)

    # Public (client) key — scrutinize_pk_... — safe to embed in frontend widgets.
    # Scoped to read-only search endpoints.
    client_key: str = Field(unique=True, index=True)

    # Allowed CORS origins for client_key — e.g. ["https://myapp.com"].
    # Empty list means no per-project CORS restriction (use global settings).
    allowed_origins: list = Field(default_factory=list, sa_column=Column(JSON))

    # Per-project pipeline overrides stored as JSON.
    # Keys: gate_model, rewriter_model, synthesis_model, decision_model,
    #       confidence_threshold, max_attempts, system_prompt_overrides.
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Secure hashed password for project login.
    password_hash: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
