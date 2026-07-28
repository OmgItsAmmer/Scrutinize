from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.deps import get_current_user, get_db_session
from app.models.conversation import ChatConversation
from app.models.tool_approval import ToolApproval
from app.models.user import User
from app.schemas.v3.approvals import ApprovalDecision, ToolApprovalRead

router = APIRouter(prefix="/approvals", tags=["v3-approvals"])


@router.get("/pending", response_model=list[ToolApprovalRead])
def list_pending_approvals(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[ToolApproval]:
    """List all pending tool approvals for the current user's conversations."""
    approvals = session.exec(
        select(ToolApproval)
        .join(ChatConversation, ToolApproval.conversation_id == ChatConversation.id)
        .where(ChatConversation.owner_user_id == user.id)
        .where(ToolApproval.status == "waiting")
    ).all()
    return list(approvals)


@router.post("/{approval_id}/decide", response_model=ToolApprovalRead)
def decide_approval(
    approval_id: UUID,
    body: ApprovalDecision,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ToolApproval:
    """Approve or reject a pending tool execution request."""
    approval = session.exec(
        select(ToolApproval)
        .join(ChatConversation, ToolApproval.conversation_id == ChatConversation.id)
        .where(ChatConversation.owner_user_id == user.id)
        .where(ToolApproval.id == approval_id)
    ).first()

    if not approval:
        raise HTTPException(
            status_code=404,
            detail="Pending tool approval not found or access denied.",
        )

    if approval.status != "waiting":
        raise HTTPException(
            status_code=400,
            detail="This tool approval request has already been decided.",
        )

    approval.status = "approved" if body.approved else "rejected"
    approval.decided_at = datetime.now(UTC)
    approval.reviewed_by = user.id

    session.add(approval)
    session.commit()
    session.refresh(approval)
    return approval
