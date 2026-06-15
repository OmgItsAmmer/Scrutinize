from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchResponse, SearchSource
from app.services.agents.router_agent import RouterAgent
from app.services.agents.synthesis_agent import SynthesisAgent
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


class SearchService:
    """Agentic RAG: router → embed → Qdrant → synthesis."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        router_agent: RouterAgent,
        synthesis_agent: SynthesisAgent,
        settings: Settings,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._router_agent = router_agent
        self._synthesis_agent = synthesis_agent
        self._settings = settings

    def search(
        self,
        query: str,
        *,
        modality_filter: FileModality | None = None,
        top_k: int | None = None,
    ) -> SearchResponse:
        stripped_query = query.strip()
        route = self._router_agent.route(stripped_query)
        effective_modality = modality_filter or route.modality_filter
        limit = top_k or self._settings.search_top_k

        query_vector = self._embedding_service.embed_texts([route.search_query])[0]
        hits = self._vector_store.search(
            query_vector,
            top_k=limit,
            modality=effective_modality.value if effective_modality else None,
        )
        sources = [_hit_to_source(hit) for hit in hits]
        answer = self._synthesis_agent.synthesize(stripped_query, sources)

        return SearchResponse(
            query=stripped_query,
            search_query=route.search_query,
            modality_filter=effective_modality,
            answer=answer,
            sources=sources,
        )


def _hit_to_source(hit: dict[str, Any]) -> SearchSource:
    payload = hit.get("payload") or {}
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    return SearchSource(
        segment_id=UUID(str(hit["id"])),
        file_id=UUID(str(payload["file_id"])),
        modality=FileModality(str(payload["modality"])),
        title=str(payload.get("title") or ""),
        content=str(payload.get("content") or ""),
        source_path=str(payload.get("source_path") or ""),
        start_time=float(start_time) if start_time is not None else None,
        end_time=float(end_time) if end_time is not None else None,
        score=float(hit["score"]),
    )
