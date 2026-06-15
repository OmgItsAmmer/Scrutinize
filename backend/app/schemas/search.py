from uuid import UUID

from pydantic import BaseModel, Field

from app.models.file import FileModality


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    modality_filter: FileModality | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


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


class SearchResponse(BaseModel):
    query: str
    search_query: str
    modality_filter: FileModality | None = None
    answer: str
    sources: list[SearchSource]
