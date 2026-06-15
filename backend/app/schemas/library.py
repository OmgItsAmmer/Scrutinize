from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.file import FileModality, FileStatus


class LibraryFileItem(BaseModel):
    id: UUID
    filename: str
    modality: FileModality
    status: FileStatus
    segment_count: int
    uploaded_at: datetime
    duration_seconds: float | None = None
    size_bytes: int | None = None


class LibraryResponse(BaseModel):
    files: list[LibraryFileItem]
    total: int
