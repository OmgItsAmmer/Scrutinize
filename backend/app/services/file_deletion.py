from uuid import UUID

from app.core.config import Settings
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.cloudinary_utils import parse_cloudinary_url
from app.services.job_orchestrator import JobOrchestrator
from app.services.vector_store import VectorStore


class FileDeletionService:
    """Remove a file and its data from Cloudinary, Qdrant, and Neon."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        storage: CloudinaryStorage,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self._orchestrator = orchestrator
        self._storage = storage
        self._vector_store = vector_store
        self._settings = settings

    def delete_file(self, file_id: UUID) -> None:
        file_record = self._orchestrator.get_file(file_id)
        if file_record is None:
            raise LookupError(f"File {file_id} not found")

        if self._settings.cloudinary_configured:
            parsed = parse_cloudinary_url(file_record.storage_path)
            if parsed is not None:
                public_id, resource_type = parsed
                self._storage.delete(public_id, resource_type=resource_type)

        self._vector_store.delete_by_file_id(file_id)
        self._orchestrator.delete_file(file_id)
