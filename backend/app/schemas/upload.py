from uuid import UUID

from pydantic import BaseModel, Field

from app.models.file import FileModality
from app.models.processing_job import JobStatus


class UploadResponse(BaseModel):
    file_id: UUID
    job_id: UUID
    filename: str
    modality: FileModality
    status: JobStatus = Field(description="Initial job status (pending)")
    message: str = "Upload accepted; processing queued"
