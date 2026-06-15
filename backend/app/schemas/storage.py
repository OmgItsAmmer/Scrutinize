from pydantic import BaseModel, Field


class StorageUploadResponse(BaseModel):
    public_id: str
    secure_url: str = Field(description="HTTPS URL for playback or download")
    resource_type: str
    bytes: int
    format: str | None = None
