from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.file import FileModality
from app.schemas.search import SearchSource


class SearchV2Route(StrEnum):
    RAG = "rag"
    GENERIC = "generic"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    timestamp: datetime | None = None


class ConversationState(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list, max_length=20)


class SearchV2Request(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    modality_filter: FileModality | None = None
    conversation: ConversationState | None = None


class SearchV2Response(BaseModel):
    query: str
    rewritten_query: str
    route: SearchV2Route
    gate_reason: str
    modality_filter: FileModality | None = None
    answer: str
    sources: list[SearchSource]
    attempts: int = Field(ge=1, le=2)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    disclaimer_appended: bool = False
    conversation: ConversationState = Field(default_factory=ConversationState)
