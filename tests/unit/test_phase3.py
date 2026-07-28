import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.tools.policy import PermissionChecker
from app.tools.execution_sandbox import execute_python_in_sandbox
from app.models.tool_approval import ToolApproval
from app.models.conversation import ChatConversation, ConversationScope, RetrievalPolicy
from app.models.user import User

@pytest.mark.unit
def test_permission_checker():
    # web_search requires member role
    assert PermissionChecker.check_permission("web_search", "member") is True
    assert PermissionChecker.check_permission("web_search", "owner") is True
    assert PermissionChecker.check_permission("web_search", "visitor") is False

    # execute_python requires owner role
    assert PermissionChecker.check_permission("execute_python", "owner") is True
    assert PermissionChecker.check_permission("execute_python", "member") is False

    # Risk level check
    assert PermissionChecker.requires_approval("execute_python") is True
    assert PermissionChecker.requires_approval("web_search") is False

@pytest.mark.unit
def test_execution_sandbox_mock():
    # Should run mock fallback locally when E2B key is empty
    code = "x = 5\ny = 10\nprint(x + y)"
    result = execute_python_in_sandbox(code)
    assert "[MOCK E2B SANDBOX OUTPUT]" in result
    assert "15" in result

@pytest.mark.unit
def test_approvals_api_endpoints(client, session: Session):
    # 1. Create a mock user
    user = User(email="test-approvals@example.com", is_verified=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    # 2. Mock authentication
    from app.core.deps import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: user

    # 3. Create a conversation owned by the user
    conv = ChatConversation(
        owner_user_id=user.id,
        scope=ConversationScope.GENERAL,
        retrieval_policy=RetrievalPolicy.WEB_ONLY,
        title="Test approvals conversation"
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)

    # 4. Create a pending tool approval for this conversation
    approval = ToolApproval(
        conversation_id=conv.id,
        tool_name="execute_python",
        arguments={"code": "print('hello')"},
        status="waiting"
    )
    session.add(approval)
    session.commit()
    session.refresh(approval)

    # 5. Call GET /v3/approvals/pending
    res = client.get("/v3/approvals/pending")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == str(approval.id)
    assert items[0]["tool_name"] == "execute_python"

    # 6. Decide on the approval: Approve it
    res = client.post(f"/v3/approvals/{approval.id}/decide", json={"approved": True})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # 7. Check DB status
    session.expire(approval)
    db_approval = session.get(ToolApproval, approval.id)
    assert db_approval.status == "approved"
    assert db_approval.reviewed_by == user.id

    client.app.dependency_overrides.pop(get_current_user, None)
