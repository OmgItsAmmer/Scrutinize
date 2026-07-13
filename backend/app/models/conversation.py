from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Enum, UniqueConstraint
from sqlmodel import Field, SQLModel


class ConversationScope(StrEnum):
    GENERAL = "general"
    PROJECT = "project"


class RetrievalPolicy(StrEnum):
    WEB_ONLY = "web_only"
    PROJECT_RAG = "project_rag"


class MessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _value_enum(enum_cls: type[StrEnum]) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
    )


class ChatConversation(SQLModel, table=True):
    __tablename__ = "chat_conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    project_id: UUID | None = Field(
        default=None, foreign_key="projects.id", index=True, ondelete="CASCADE"
    )
    scope: ConversationScope = Field(sa_column=Column(_value_enum(ConversationScope), nullable=False))
    retrieval_policy: RetrievalPolicy = Field(
        sa_column=Column(_value_enum(RetrievalPolicy), nullable=False)
    )
    title: str = Field(default="New chat", max_length=160)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    archived_at: datetime | None = None


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "client_message_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(
        foreign_key="chat_conversations.id", index=True, ondelete="CASCADE"
    )
    role: str = Field(max_length=16)
    content: str
    status: MessageStatus = Field(
        default=MessageStatus.COMPLETED,
        sa_column=Column(_value_enum(MessageStatus), nullable=False),
    )
    client_message_id: UUID | None = Field(default=None)
    citations: list = Field(default_factory=list, sa_column=Column(JSON))
    pipeline_run_id: UUID | None = Field(default=None, foreign_key="pipeline_runs.id")
    error_code: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    completed_at: datetime | None = None
