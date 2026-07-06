from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ApiException, UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
    SparseVector,
    SparseVectorParams,
    SparseIndexParams,
    Prefetch,
    FusionQuery,
    Fusion,
)

from app.core.config import Settings
from app.services.keyword_search_utils import build_sparse_index_text
from app.services.qdrant_errors import format_qdrant_error


@dataclass(frozen=True)
class VectorSegment:
    id: UUID
    vector: list[float]
    file_id: UUID
    project_id: UUID  # Track project ownership for multi-tenant isolation.
    modality: str
    content: str
    source_path: str
    title: str
    start_time: float | None = None
    end_time: float | None = None
    created_at: datetime | None = None
    sparse_vector: SparseVector | dict[str, Any] | None = None


@dataclass(frozen=True)
class HybridSearchResult:
    """Dense+sparse prefetch lists and client-side RRF fused hits."""

    hits: list[dict[str, Any]]
    dense_hits: list[dict[str, Any]]
    sparse_hits: list[dict[str, Any]]
    stats: Any  # RetrievalStats — typed lazily to avoid circular import


class VectorStore:
    """Qdrant client wrapper for the segments collection."""

    TEXT_VECTOR_NAME = "text_vector"

    def __init__(self, settings: Settings) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url.rstrip("/"),
            api_key=settings.qdrant_api_key or None,
            check_compatibility=False,
        )
        self._collection = settings.qdrant_collection
        self._vector_size = settings.embedding_dimensions
        self._sparse_model = None

    @property
    def sparse_model(self) -> Any:
        if self._sparse_model is None:
            from fastembed import SparseTextEmbedding
            self._sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        return self._sparse_model

    def collection_exists(self) -> bool:
        return self._client.collection_exists(self._collection)

    def create_collection(self) -> None:
        if self.collection_exists():
            try:
                info = self._client.get_collection(self._collection)
                params = getattr(info.config, "params", None)
                sparse_config = getattr(params, "sparse_vectors", None)
                if not sparse_config or "sparse_vector" not in sparse_config:
                    self._client.delete_collection(self._collection)
                else:
                    return
            except Exception:
                return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                self.TEXT_VECTOR_NAME: VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse_vector": SparseVectorParams(
                    index=SparseIndexParams(
                        on_disk=True,
                    )
                )
            },
        )

    def _ensure_payload_indexes(self) -> None:
        """Qdrant Cloud requires payload indexes before filter/delete on fields."""
        if not self.collection_exists():
            return

        for field_name in ("file_id", "modality", "project_id"):  # project_id indexed for tenant isolation
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except UnexpectedResponse as exc:
                # Index already exists — safe to ignore.
                if exc.status_code not in {400, 409}:
                    raise
                message = str(exc).lower()
                if "already exists" not in message and "already indexed" not in message:
                    raise

    def ensure_collection(self) -> None:
        try:
            self.create_collection()
            self._ensure_payload_indexes()
        except (UnexpectedResponse, ApiException) as exc:
            raise RuntimeError(format_qdrant_error(exc)) from exc

    def upsert_segments(self, segments: list[VectorSegment]) -> None:
        if not segments:
            return

        self.ensure_collection()

        # Identify segments that need sparse vectors generated
        missing_sparse = [s for s in segments if s.sparse_vector is None]
        sparse_vectors = {}
        if missing_sparse:
            texts = [
                build_sparse_index_text(
                    content=segment.content,
                    title=segment.title,
                    source_path=segment.source_path,
                )
                for segment in missing_sparse
            ]
            embeddings = list(self.sparse_model.embed(texts))
            for segment, emb in zip(missing_sparse, embeddings):
                sparse_vectors[segment.id] = SparseVector(
                    indices=list(emb.indices),
                    values=list(emb.values)
                )

        points = []
        for segment in segments:
            sv = segment.sparse_vector
            if sv is None:
                sv = sparse_vectors.get(segment.id)
            elif not isinstance(sv, SparseVector):
                if isinstance(sv, dict):
                    sv = SparseVector(indices=sv["indices"], values=sv["values"])

            vector_dict = {
                self.TEXT_VECTOR_NAME: segment.vector,
            }
            if sv is not None:
                vector_dict["sparse_vector"] = sv

            points.append(
                PointStruct(
                    id=str(segment.id),
                    vector=vector_dict,
                    payload={
                        "file_id": str(segment.file_id),
                        "project_id": str(segment.project_id),  # tenant isolation key
                        "modality": segment.modality,
                        "content": segment.content,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "source_path": segment.source_path,
                        "title": segment.title,
                        "created_at": (
                            segment.created_at or datetime.now(UTC)
                        ).isoformat(),
                    },
                )
            )

        self._client.upsert(collection_name=self._collection, points=points)

    def _build_query_filter(
        self,
        *,
        project_id: UUID,
        modality: str | None,
    ) -> Filter:
        must_conditions: list[FieldCondition] = [
            FieldCondition(key="project_id", match=MatchValue(value=str(project_id)))
        ]
        if modality is not None:
            must_conditions.append(
                FieldCondition(key="modality", match=MatchValue(value=modality))
            )
        return Filter(must=must_conditions)

    @staticmethod
    def _normalize_sparse_vector(
        query_sparse_vector: SparseVector | dict[str, Any],
    ) -> SparseVector:
        sv = query_sparse_vector
        if not isinstance(sv, SparseVector):
            if isinstance(sv, dict):
                return SparseVector(indices=sv["indices"], values=sv["values"])
            if hasattr(sv, "indices") and hasattr(sv, "values"):
                return SparseVector(indices=list(sv.indices), values=list(sv.values))
        return sv

    @staticmethod
    def _points_to_hits(points: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in points
        ]

    def search(
        self,
        query_vector: list[float],
        *,
        project_id: UUID,  # Mandatory — every search is scoped to a single project.
        top_k: int = 10,
        modality: str | None = None,
        query_sparse_vector: SparseVector | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        query_filter = self._build_query_filter(project_id=project_id, modality=modality)

        if query_sparse_vector is not None:
            sv = self._normalize_sparse_vector(query_sparse_vector)

            prefetch = [
                Prefetch(
                    query=query_vector,
                    using=self.TEXT_VECTOR_NAME,
                    limit=top_k,
                ),
                Prefetch(
                    query=sv,
                    using="sparse_vector",
                    limit=top_k,
                ),
            ]
            response = self._client.query_points(
                collection_name=self._collection,
                prefetch=prefetch,
                query=FusionQuery(fusion=Fusion.RRF),
                limit=top_k,
                query_filter=query_filter,
            )
        else:
            response = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                using=self.TEXT_VECTOR_NAME,
                limit=top_k,
                query_filter=query_filter,
            )

        return self._points_to_hits(response.points)

    def search_hybrid(
        self,
        query_vector: list[float],
        *,
        project_id: UUID,
        top_k: int = 10,
        modality: str | None = None,
        query_sparse_vector: SparseVector | dict[str, Any],
        rrf_k: int = 60,
    ) -> HybridSearchResult:
        """Run separate dense and sparse prefetches, fuse with RRF, return all lists."""
        from app.services.v2.retrieval_utils import fuse_rrf_hits

        self.ensure_collection()
        query_filter = self._build_query_filter(project_id=project_id, modality=modality)
        sv = self._normalize_sparse_vector(query_sparse_vector)

        dense_response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            using=self.TEXT_VECTOR_NAME,
            limit=top_k,
            query_filter=query_filter,
        )
        sparse_response = self._client.query_points(
            collection_name=self._collection,
            query=sv,
            using="sparse_vector",
            limit=top_k,
            query_filter=query_filter,
        )

        dense_hits = self._points_to_hits(dense_response.points)
        sparse_hits = self._points_to_hits(sparse_response.points)
        sparse_dims = len(sv.indices) if sv.indices is not None else 0

        fused_hits, stats = fuse_rrf_hits(
            dense_hits,
            sparse_hits,
            k=rrf_k,
            top_k=top_k,
            sparse_query_dimensions=sparse_dims,
        )
        return HybridSearchResult(
            hits=fused_hits,
            dense_hits=dense_hits,
            sparse_hits=sparse_hits,
            stats=stats,
        )

    def count_points(self) -> int:
        if not self.collection_exists():
            return 0
        info = self._client.get_collection(self._collection)
        return info.points_count or 0

    def delete_by_file_id(self, file_id: UUID) -> None:
        if not self.collection_exists():
            return
        self._ensure_payload_indexes()
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="file_id",
                            match=MatchValue(value=str(file_id)),
                        )
                    ]
                )
            ),
        )
