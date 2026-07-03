from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.file import FileModality
from app.schemas.search import SearchSource


@dataclass(frozen=True)
class RetrievalStats:
    """Counts for hybrid dense (semantic) + sparse (keyword) retrieval and RRF fusion."""

    semantic_prefetch_count: int = 0
    keyword_prefetch_count: int = 0
    qdrant_retrieved_count: int = 0
    rrf_k: int = 60
    rrf_semantic_only: int = 0
    rrf_keyword_only: int = 0
    rrf_both_lists: int = 0
    sparse_query_dimensions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_prefetch_count": self.semantic_prefetch_count,
            "keyword_prefetch_count": self.keyword_prefetch_count,
            "qdrant_retrieved_count": self.qdrant_retrieved_count,
            "sparse_query_dimensions": self.sparse_query_dimensions,
            "rrf": {
                "k": self.rrf_k,
                "fused_count": self.qdrant_retrieved_count,
                "semantic_only": self.rrf_semantic_only,
                "keyword_only": self.rrf_keyword_only,
                "both_lists": self.rrf_both_lists,
            },
        }

    @classmethod
    def empty(cls, *, rrf_k: int = 60) -> "RetrievalStats":
        return cls(rrf_k=rrf_k)


@dataclass(frozen=True)
class RetrieveResult:
    sources: list[SearchSource]
    stats: RetrievalStats
    source_rank_fields: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0


def hit_to_source(hit: dict[str, Any]) -> SearchSource:
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


def _point_id(hit: dict[str, Any]) -> str:
    return str(hit["id"])


def fuse_rrf_hits(
    dense_hits: list[dict[str, Any]],
    sparse_hits: list[dict[str, Any]],
    *,
    k: int = 60,
    top_k: int = 5,
    sparse_query_dimensions: int = 0,
) -> tuple[list[dict[str, Any]], RetrievalStats]:
    """Fuse dense (semantic) and sparse (keyword/BM25) lists with RRF."""
    dense_ranks = {_point_id(hit): rank for rank, hit in enumerate(dense_hits, start=1)}
    sparse_ranks = {_point_id(hit): rank for rank, hit in enumerate(sparse_hits, start=1)}

    hit_by_id: dict[str, dict[str, Any]] = {}
    for hit in dense_hits + sparse_hits:
        hit_by_id[_point_id(hit)] = hit

    scores: dict[str, float] = {}
    for point_id in set(dense_ranks) | set(sparse_ranks):
        score = 0.0
        if point_id in dense_ranks:
            score += 1.0 / (k + dense_ranks[point_id])
        if point_id in sparse_ranks:
            score += 1.0 / (k + sparse_ranks[point_id])
        scores[point_id] = score

    sorted_ids = sorted(scores, key=lambda pid: scores[pid], reverse=True)[:top_k]

    semantic_only = keyword_only = both_lists = 0
    fused: list[dict[str, Any]] = []
    for point_id in sorted_ids:
        in_semantic = point_id in dense_ranks
        in_keyword = point_id in sparse_ranks
        if in_semantic and in_keyword:
            both_lists += 1
        elif in_semantic:
            semantic_only += 1
        elif in_keyword:
            keyword_only += 1

        base = dict(hit_by_id[point_id])
        base["score"] = scores[point_id]
        base["semantic_rank"] = dense_ranks.get(point_id)
        base["keyword_rank"] = sparse_ranks.get(point_id)
        fused.append(base)

    stats = RetrievalStats(
        semantic_prefetch_count=len(dense_hits),
        keyword_prefetch_count=len(sparse_hits),
        qdrant_retrieved_count=len(fused),
        rrf_k=k,
        rrf_semantic_only=semantic_only,
        rrf_keyword_only=keyword_only,
        rrf_both_lists=both_lists,
        sparse_query_dimensions=sparse_query_dimensions,
    )
    return fused, stats


def source_log_fields(hit: dict[str, Any]) -> dict[str, Any]:
    """Extra per-source rank fields for pipeline retrieval logging."""
    return {
        "semantic_rank": hit.get("semantic_rank"),
        "keyword_rank": hit.get("keyword_rank"),
        "in_semantic_list": hit.get("semantic_rank") is not None,
        "in_keyword_list": hit.get("keyword_rank") is not None,
    }
