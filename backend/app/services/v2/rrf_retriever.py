import logging
import time
from uuid import UUID

from app.core.config import Settings
from app.models.file import FileModality
from app.services.embedding_service import EmbeddingService
from app.services.keyword_search_utils import embed_sparse_query
from app.services.v2.retrieval_utils import (
    RetrieveResult,
    RetrievalStats,
    hit_to_source,
    source_log_fields,
)
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


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
    ) -> RetrieveResult:
        query = rewritten_query.strip()
        if not query:
            return RetrieveResult(sources=[], stats=RetrievalStats.empty(rrf_k=self._settings.v2_rrf_k))

        started = time.monotonic()
        limit = top_k or self._settings.v2_rrf_top_k
        vector = self._embedding_service.embed_texts([query])[0]
        sparse_emb = embed_sparse_query(self._vector_store.sparse_model, query)

        modality = modality_filter.value if modality_filter else None
        hybrid = self._vector_store.search_hybrid(
            vector,
            project_id=project_id,
            top_k=limit,
            modality=modality,
            query_sparse_vector=sparse_emb,
            rrf_k=self._settings.v2_rrf_k,
        )
        sources = [hit_to_source(hit) for hit in hybrid.hits]
        source_rank_fields = [source_log_fields(hit) for hit in hybrid.hits]
        latency_ms = int((time.monotonic() - started) * 1000)

        logger.info(
            "v2 retrieval %s",
            {
                **hybrid.stats.to_dict(),
                "latency_ms": latency_ms,
                "rewritten_query": query,
            },
        )

        return RetrieveResult(
            sources=sources,
            stats=hybrid.stats,
            source_rank_fields=source_rank_fields,
            latency_ms=latency_ms,
        )
