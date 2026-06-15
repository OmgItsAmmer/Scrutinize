from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.file import FileModality
from app.models.processing_job import JobStatus


class SegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    modality: FileModality
    content: str
    start_time: float | None
    end_time: float | None
    created_at: datetime


class SegmentCreate(BaseModel):
    file_id: UUID
    modality: FileModality
    content: str = Field(min_length=1)
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, ge=0)
    segment_id: UUID | None = None
