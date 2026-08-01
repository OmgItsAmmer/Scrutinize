import logging
import time
from dataclasses import replace
from uuid import UUID
from langsmith import traceable

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
from app.services.v5.reranker import Reranker
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RrfRetriever:
    """Qdrant dense+sparse retrieval using the rewritten query, scoped to a project."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        settings: Settings,
        reranker: Reranker | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings
        self._reranker = reranker or Reranker(settings)

    @traceable(name="RrfRetriever.retrieve", run_type="retriever")
    def retrieve(
        self,
        rewritten_query: str,
        *,
        project_id: UUID,  # Mandatory — enforce per-project document isolation.
        modality_filter: FileModality | None = None,
        top_k: int | None = None,
        conversation_id: UUID | None = None,
        include_project_wide: bool = True,
        apply_rerank: bool | None = None,
    ) -> RetrieveResult:
        query = rewritten_query.strip()
        if not query:
            return RetrieveResult(sources=[], stats=RetrievalStats.empty(rrf_k=self._settings.v2_rrf_k))

        started = time.monotonic()
        final_top_k = top_k or self._settings.v2_rrf_top_k
        # Callers that only need an approximate top score (e.g. the retrieval
        # precheck) can opt out of reranking — it's the expensive part of this
        # call and its precision doesn't matter for a threshold comparison.
        rerank_enabled = self._settings.rerank_enabled if apply_rerank is None else apply_rerank
        # Widen the post-fusion cut when reranking so it has a real candidate pool to work with.
        fusion_top_k = max(final_top_k, self._settings.rerank_candidate_pool) if rerank_enabled else final_top_k
        vector = self._embedding_service.embed_texts([query])[0]
        sparse_emb = embed_sparse_query(self._vector_store.sparse_model, query)

        modality = modality_filter.value if modality_filter else None
        hybrid = self._vector_store.search_hybrid(
            vector,
            project_id=project_id,
            top_k=fusion_top_k,
            prefetch_limit=self._settings.v2_rrf_prefetch_limit,
            modality=modality,
            query_sparse_vector=sparse_emb,
            rrf_k=self._settings.v2_rrf_k,
            conversation_id=conversation_id,
            include_project_wide=include_project_wide,
        )
        sources = [hit_to_source(hit) for hit in hybrid.hits]
        source_rank_fields = [source_log_fields(hit) for hit in hybrid.hits]

        rerank_applied = False
        rerank_latency_ms = 0
        rerank_error: str | None = None
        if rerank_enabled and sources:
            rerank_result = self._reranker.rerank(query, sources, top_k=final_top_k)
            rerank_applied = rerank_result.applied
            rerank_latency_ms = rerank_result.latency_ms
            rerank_error = rerank_result.error
            reordered = [item.source for item in rerank_result.sources]
            reordered_rank_fields = []
            for item in rerank_result.sources:
                original_index = item.rrf_rank - 1
                fields = dict(source_rank_fields[original_index]) if original_index < len(source_rank_fields) else {}
                fields["rrf_rank"] = item.rrf_rank
                fields["rerank_score"] = item.rerank_score
                reordered_rank_fields.append(fields)
            sources = reordered
            source_rank_fields = reordered_rank_fields
        else:
            sources = sources[:final_top_k]
            source_rank_fields = source_rank_fields[:final_top_k]

        stats = replace(
            hybrid.stats,
            rerank_applied=rerank_applied,
            rerank_latency_ms=rerank_latency_ms,
            rerank_error=rerank_error,
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        logger.info(
            "v2 retrieval %s",
            {
                **stats.to_dict(),
                "latency_ms": latency_ms,
                "rewritten_query": query,
            },
        )

        return RetrieveResult(
            sources=sources,
            stats=stats,
            source_rank_fields=source_rank_fields,
            latency_ms=latency_ms,
            rerank_applied=rerank_applied,
            rerank_latency_ms=rerank_latency_ms,
            rerank_error=rerank_error,
        )
