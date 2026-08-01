from uuid import UUID

from pydantic import BaseModel, Field

from app.models.file import FileModality
from app.models.processing_job import JobStatus


class UploadResponse(BaseModel):
    file_id: UUID
    job_id: UUID | None = None
    filename: str
    modality: FileModality
    status: JobStatus | str = Field(description="Initial job status (pending)")
    message: str = "Upload accepted; processing queued"
    duplicate_of: UUID | None = None
