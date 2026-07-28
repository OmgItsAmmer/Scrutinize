from datetime import UTC, datetime
from uuid import UUID, uuid4
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

class ToolApproval(SQLModel, table=True):
    __tablename__ = "tool_approvals"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(foreign_key="chat_conversations.id", index=True, ondelete="CASCADE")
    message_id: UUID | None = Field(default=None, foreign_key="chat_messages.id", ondelete="CASCADE", nullable=True)
    tool_name: str = Field(max_length=255)
    arguments: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="waiting", max_length=50) # waiting, approved, rejected
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    reviewed_by: UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL", nullable=True)
