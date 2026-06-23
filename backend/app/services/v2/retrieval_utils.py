from typing import Any
from uuid import UUID

from app.models.file import FileModality
from app.schemas.search import SearchSource


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
