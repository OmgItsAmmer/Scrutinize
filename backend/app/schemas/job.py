from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.processing_job import JobStatus


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    stage: str
    status: JobStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime
