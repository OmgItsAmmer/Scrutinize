from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import Settings


@dataclass(frozen=True)
class VectorSegment:
    id: UUID
    vector: list[float]
    file_id: UUID
    modality: str
    content: str
    source_path: str
    title: str
    start_time: float | None = None
    end_time: float | None = None
    created_at: datetime | None = None


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

    def collection_exists(self) -> bool:
        return self._client.collection_exists(self._collection)

    def create_collection(self) -> None:
        if self.collection_exists():
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                self.TEXT_VECTOR_NAME: VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                )
            },
        )

    def ensure_collection(self) -> None:
        self.create_collection()

    def upsert_segments(self, segments: list[VectorSegment]) -> None:
        if not segments:
            return

        self.ensure_collection()
        points = [
            PointStruct(
                id=str(segment.id),
                vector={self.TEXT_VECTOR_NAME: segment.vector},
                payload={
                    "file_id": str(segment.file_id),
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
            for segment in segments
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        modality: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        query_filter = None
        if modality is not None:
            query_filter = Filter(
                must=[FieldCondition(key="modality", match=MatchValue(value=modality))]
            )

        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            using=self.TEXT_VECTOR_NAME,
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in response.points
        ]

    def count_points(self) -> int:
        if not self.collection_exists():
            return 0
        info = self._client.get_collection(self._collection)
        return info.points_count or 0

    def delete_by_file_id(self, file_id: UUID) -> None:
        if not self.collection_exists():
            return
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
