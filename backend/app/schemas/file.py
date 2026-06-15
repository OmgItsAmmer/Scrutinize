from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    modality: FileModality
    storage_path: str
    duration_seconds: float | None
    size_bytes: int | None
    status: FileStatus
    uploaded_at: datetime


class FileCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    modality: FileModality
    storage_path: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class JobCreate(BaseModel):
    file_id: UUID
    stage: str = Field(min_length=1, max_length=128)
