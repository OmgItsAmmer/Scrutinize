from uuid import UUID

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.services.embedding_service import EmbeddingService
from app.services.v2.retrieval_utils import hit_to_source
from app.services.vector_store import VectorStore


class RrfRetriever:
    """Qdrant dense+sparse retrieval using the rewritten query, scoped to a project."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings

    def retrieve(
        self,
        rewritten_query: str,
        *,
        project_id: UUID,  # Mandatory — enforce per-project document isolation.
        modality_filter: FileModality | None = None,
        top_k: int | None = None,
    ) -> list[SearchSource]:
        query = rewritten_query.strip()
        if not query:
            return []

        limit = top_k or self._settings.v2_rrf_top_k
        vector = self._embedding_service.embed_texts([query])[0]

        from qdrant_client.models import SparseVector

        # Generate sparse vector for query
        sparse_raw = list(self._vector_store.sparse_model.embed([query]))[0]
        sparse_emb = SparseVector(
            indices=list(sparse_raw.indices),
            values=list(sparse_raw.values),
        )

        modality = modality_filter.value if modality_filter else None
        hits = self._vector_store.search(
            vector,
            project_id=project_id,
            top_k=limit,
            modality=modality,
            query_sparse_vector=sparse_emb,
        )
        return [hit_to_source(hit) for hit in hits]

