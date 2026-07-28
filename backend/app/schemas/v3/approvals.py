from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class ToolApprovalRead(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID | None = None
    tool_name: str
    arguments: dict
    status: str
    created_at: datetime
    decided_at: datetime | None = None
    reviewed_by: UUID | None = None

    class Config:
        from_attributes = True

class ApprovalDecision(BaseModel):
    approved: bool = Field(..., description="Whether to approve (true) or reject (false) the execution of the tool.")
