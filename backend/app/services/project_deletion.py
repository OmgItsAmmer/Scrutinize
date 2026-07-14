from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import Settings
from app.models.conversation import ChatConversation, ChatMessage
from app.models.project import Project
from app.models.user import ProjectMember, User
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.file_deletion import FileDeletionService
from app.services.job_orchestrator import JobOrchestrator
from app.services.vector_store import VectorStore


class ProjectDeletionService:
    """Delete a project and all associated indexed files."""

    def __init__(
        self,
        session: Session,
        orchestrator: JobOrchestrator,
        storage: CloudinaryStorage,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self._session = session
        self._orchestrator = orchestrator
        self._file_deletion = FileDeletionService(
            orchestrator, storage, vector_store, settings
        )

    def _delete_project_conversations(self, project_id: UUID) -> None:
        conversations = list(
            self._session.exec(
                select(ChatConversation).where(ChatConversation.project_id == project_id)
            )
        )
        for conversation in conversations:
            messages = list(
                self._session.exec(
                    select(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
                )
            )
            for message in messages:
                self._session.delete(message)
            self._session.delete(conversation)
        self._session.flush()

    def delete_for_user(self, user: User, project_id: UUID) -> None:
        member = self._session.get(ProjectMember, (user.id, project_id))
        if member is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if member.role != "owner":
            raise HTTPException(status_code=403, detail="Only project owners can delete projects")

        project = self._session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        while True:
            files = self._orchestrator.list_files(limit=100, offset=0, project_id=project_id)
            if not files:
                break
            for file_record in files:
                try:
                    self._file_deletion.delete_file(file_record.id)
                except LookupError:
                    continue

        self._delete_project_conversations(project_id)
        self._session.delete(project)
        self._session.commit()
