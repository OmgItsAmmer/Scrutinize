from uuid import UUID

from pydantic import BaseModel, Field

from app.models.file import FileModality




class SearchSource(BaseModel):
    segment_id: UUID
    file_id: UUID
    modality: FileModality
    title: str
    content: str
    source_path: str
    start_time: float | None = None
    end_time: float | None = None
    score: float
    page_number: int | None = None
    section_path: str | None = None
    is_poisoned: bool = False



