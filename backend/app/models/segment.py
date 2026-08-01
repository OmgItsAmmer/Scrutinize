from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.file import FileModality


class Segment(SQLModel, table=True):
    __tablename__ = "segments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    file_id: UUID = Field(foreign_key="files.id", index=True)
    # Multi-tenant: denormalized for fast per-project DB queries (avoid join through files).
    # Nullable for legacy rows that predate multi-tenancy.
    project_id: UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    conversation_id: UUID | None = Field(
        default=None, foreign_key="chat_conversations.id", index=True
    )
    modality: FileModality
    content: str
    start_time: float | None = None
    end_time: float | None = None
    # V5 M4 — page/section position metadata (nullable for pre-V5 rows).
    page_number: int | None = None
    section_path: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    block_type: str | None = None
    # V5 Phase 3 M6 — generated situating header (embedded, never shown/cited as content).
    context_header: str | None = None
    # V5 Phase 3 M7 — which ingestion pipeline generation produced this segment,
    # so mixed-generation corpora are diagnosable during a staged reindex rollout.
    pipeline_version: int = 1
    is_poisoned: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

