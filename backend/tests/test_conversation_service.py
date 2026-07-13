from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.conversation import ChatConversation, ChatMessage, ConversationScope, MessageStatus, RetrievalPolicy
from app.models.pipeline_log import PipelineRun  # noqa: F401
from app.models.project import Project
from app.models.user import ProjectMember, User
from app.services.conversation_service import ConversationService


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _user(session: Session, email: str) -> User:
    user = User(email=email, is_verified=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_scope_enforces_retrieval_policy_and_project_membership(session: Session):
    owner = _user(session, "owner@example.com")
    project = Project(name="Research", api_key="sk-test", client_key="pk-test")
    session.add(project)
    session.commit()
    session.refresh(project)
    session.add(ProjectMember(user_id=owner.id, project_id=project.id, role="owner"))
    session.commit()

    service = ConversationService(session)
    general = service.create(owner, scope="general", project_id=None, title=None)
    project_chat = service.create(
        owner, scope="project", project_id=project.id, title="Project chat"
    )

    assert general.scope == ConversationScope.GENERAL
    assert general.project_id is None
    assert general.retrieval_policy == RetrievalPolicy.WEB_ONLY
    assert project_chat.scope == ConversationScope.PROJECT
    assert project_chat.project_id == project.id
    assert project_chat.retrieval_policy == RetrievalPolicy.PROJECT_RAG


def test_conversations_are_private_and_turn_retries_are_idempotent(session: Session):
    owner = _user(session, "owner2@example.com")
    stranger = _user(session, "stranger@example.com")
    service = ConversationService(session)
    conversation = service.create(owner, scope="general", project_id=None, title=None)
    client_id = uuid4()

    _, first_user, first_assistant = service.begin_turn(
        owner, conversation.id, "What changed today?", client_id
    )
    _, retried_user, retried_assistant = service.begin_turn(
        owner, conversation.id, "What changed today?", client_id
    )

    assert first_user.id == retried_user.id
    assert first_assistant.id == retried_assistant.id
    with pytest.raises(HTTPException) as exc:
        service.get(stranger, conversation.id)
    assert exc.value.status_code == 404


def test_conversation_enums_persist_lowercase_values():
    assert ChatConversation.__table__.c.scope.type.enums == ["general", "project"]
    assert ChatConversation.__table__.c.retrieval_policy.type.enums == [
        "web_only",
        "project_rag",
    ]
    assert ChatMessage.__table__.c.status.type.enums == [
        MessageStatus.PENDING.value,
        MessageStatus.STREAMING.value,
        MessageStatus.COMPLETED.value,
        MessageStatus.FAILED.value,
        MessageStatus.CANCELLED.value,
    ]
