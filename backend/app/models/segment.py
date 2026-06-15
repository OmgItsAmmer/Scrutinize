from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.file import FileModality


class Segment(SQLModel, table=True):
    __tablename__ = "segments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    file_id: UUID = Field(foreign_key="files.id", index=True)
    modality: FileModality
    content: str
    start_time: float | None = None
    end_time: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
