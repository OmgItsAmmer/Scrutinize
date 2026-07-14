from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, or_, select

from app.models.conversation import (
    ChatConversation,
    ChatMessage,
    ConversationScope,
    MessageStatus,
    RetrievalPolicy,
)
from app.models.user import ProjectMember, User
from app.models.file import File, FileStatus


class ConversationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _verify_project(self, user: User, project_id: UUID) -> None:
        if self.session.get(ProjectMember, (user.id, project_id)) is None:
            raise HTTPException(status_code=404, detail="Project not found")

    def create(
        self, user: User, *, scope: str, project_id: UUID | None, title: str | None
    ) -> ChatConversation:
        if scope == ConversationScope.PROJECT:
            assert project_id is not None
            self._verify_project(user, project_id)
            policy = RetrievalPolicy.PROJECT_RAG
        else:
            project_id = None
            policy = RetrievalPolicy.WEB_ONLY
        item = ChatConversation(
            owner_user_id=user.id,
            project_id=project_id,
            scope=ConversationScope(scope),
            retrieval_policy=policy,
            title=(title or "New chat").strip() or "New chat",
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get(self, user: User, conversation_id: UUID) -> ChatConversation:
        item = self.session.get(ChatConversation, conversation_id)
        if item is None or item.owner_user_id != user.id or item.archived_at is not None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if item.project_id is not None:
            self._verify_project(user, item.project_id)
        return item

    def list(
        self,
        user: User,
        *,
        scope: str | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ChatConversation]:
        statement = select(ChatConversation).where(
            ChatConversation.owner_user_id == user.id,
            col(ChatConversation.archived_at).is_(None),
        )
        if scope:
            statement = statement.where(ChatConversation.scope == scope)
        if project_id:
            self._verify_project(user, project_id)
            statement = statement.where(ChatConversation.project_id == project_id)
        ordered = statement.order_by(ChatConversation.updated_at.desc()).limit(limit)
        return list(self.session.exec(ordered))

    def patch(
        self,
        user: User,
        conversation_id: UUID,
        *,
        title: str | None,
        archived: bool | None,
    ) -> ChatConversation:
        item = self.get(user, conversation_id)
        if title is not None:
            item.title = title.strip()
        if archived is not None:
            item.archived_at = datetime.now(UTC) if archived else None
        item.updated_at = datetime.now(UTC)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def delete(self, user: User, conversation_id: UUID) -> None:
        self.patch(user, conversation_id, title=None, archived=True)

    def messages(self, user: User, conversation_id: UUID, limit: int = 100) -> list[ChatMessage]:
        self.get(user, conversation_id)
        statement = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return list(self.session.exec(statement))

    def begin_turn(
        self,
        user: User,
        conversation_id: UUID,
        content: str,
        client_message_id: UUID,
        *,
        title_hint: str | None = None,
    ) -> tuple[ChatConversation, ChatMessage, ChatMessage]:
        conversation = self.get(user, conversation_id)
        existing = self.session.exec(
            select(ChatMessage).where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.client_message_id == client_message_id,
            )
        ).first()
        if existing:
            assistant = self.session.exec(
                select(ChatMessage).where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.created_at >= existing.created_at,
                ).order_by(ChatMessage.created_at.asc())
            ).first()
            if assistant:
                return conversation, existing, assistant
        now = datetime.now(UTC)
        user_message = ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=content.strip(),
            status=MessageStatus.COMPLETED,
            client_message_id=client_message_id,
            completed_at=now,
        )
        assistant = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            status=MessageStatus.STREAMING,
        )
        if conversation.title == "New chat":
            title_source = (title_hint or content.strip() or "New chat")
            conversation.title = title_source[:80]
        conversation.updated_at = now
        self.session.add(user_message)
        self.session.add(assistant)
        self.session.add(conversation)
        self.session.commit()
        self.session.refresh(user_message)
        self.session.refresh(assistant)
        return conversation, user_message, assistant

    def complete(self, assistant: ChatMessage, content: str, citations: list | None = None) -> None:
        assistant.content = content
        assistant.citations = citations or []
        assistant.status = MessageStatus.COMPLETED
        assistant.completed_at = datetime.now(UTC)
        self.session.add(assistant)
        conversation = self.session.get(ChatConversation, assistant.conversation_id)
        if conversation:
            conversation.updated_at = assistant.completed_at
            self.session.add(conversation)
        self.session.commit()

    def fail(self, assistant: ChatMessage, code: str) -> None:
        assistant.status = MessageStatus.FAILED
        assistant.error_code = code
        assistant.completed_at = datetime.now(UTC)
        self.session.add(assistant)
        self.session.commit()

    def has_indexed_sources(
        self, conversation_id: UUID, project_id: UUID | None = None
    ) -> bool:
        conditions = [File.conversation_id == conversation_id]
        if project_id is not None:
            conditions.append(File.project_id == project_id)
        statement = (
            select(File.id)
            .where(File.status == FileStatus.INDEXED)
            .where(or_(*conditions))
            .limit(1)
        )
        return self.session.exec(statement).first() is not None

    def list_sources(self, user: User, conversation_id: UUID) -> list[File]:
        conversation = self.get(user, conversation_id)
        statement = (
            select(File)
            .where(File.conversation_id == conversation.id)
            .order_by(File.uploaded_at.desc())
        )
        return list(self.session.exec(statement).all())
