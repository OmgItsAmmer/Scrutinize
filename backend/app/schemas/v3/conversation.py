from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ConversationCreate(BaseModel):
    scope: Literal["general", "project"]
    project_id: UUID | None = None
    title: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "general" and self.project_id is not None:
            raise ValueError("General conversations cannot belong to a project")
        if self.scope == "project" and self.project_id is None:
            raise ValueError("Project conversations require project_id")
        return self


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    archived: bool | None = None


class ConversationRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    project_id: UUID | None
    scope: str
    retrieval_policy: str
    title: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ConversationList(BaseModel):
    conversations: list[ConversationRead]
    total: int


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=32000)
    client_message_id: UUID
    requested_tool: str | None = Field(default=None, max_length=64)
    web_search_mode: Literal["always", "never"] = "never"
    use_cloud_llm: bool | None = None

    @model_validator(mode="after")
    def validate_content_or_tool(self):
        if not self.content.strip() and not self.requested_tool:
            raise ValueError("Either content or requested_tool is required")
        return self


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    status: str
    citations: list = Field(default_factory=list)
    pipeline_run_id: UUID | None = None
    created_at: datetime
    completed_at: datetime | None


class MessageList(BaseModel):
    messages: list[MessageRead]
    total: int


class ConversationSourceRead(BaseModel):
    file_id: UUID
    filename: str
    modality: str
    status: str
    uploaded_at: datetime


class ConversationSourceList(BaseModel):
    sources: list[ConversationSourceRead]
    total: int
