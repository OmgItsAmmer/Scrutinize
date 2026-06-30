from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class FileModality(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"


class FileStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class File(SQLModel, table=True):
    __tablename__ = "files"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Multi-tenant: link to owning project. Nullable for legacy rows.
    project_id: UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    filename: str
    modality: FileModality
    storage_path: str
    duration_seconds: float | None = None
    size_bytes: int | None = None
    status: FileStatus = Field(default=FileStatus.UPLOADED)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
