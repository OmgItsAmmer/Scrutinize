from dataclasses import dataclass
from uuid import UUID, uuid4

from app.models.file import File, FileModality
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.vector_store import VectorSegment, VectorStore


@dataclass(frozen=True)
class TimedContent:
    content: str
    start_time: float | None = None
    end_time: float | None = None


def index_segments(
    orchestrator: JobOrchestrator,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    file_record: File,
    segments: list[TimedContent],
    modality: FileModality,
) -> int:
    if not segments:
        raise ValueError("No segments to index")

    texts = [segment.content for segment in segments]
    vectors = embedding_service.embed_texts(texts)
    vector_segments: list[VectorSegment] = []

    for segment, vector in zip(segments, vectors, strict=True):
        segment_id = uuid4()
        orchestrator.create_segment(
            file_id=file_record.id,
            modality=modality,
            content=segment.content,
            start_time=segment.start_time,
            end_time=segment.end_time,
            segment_id=segment_id,
        )
        vector_segments.append(
            VectorSegment(
                id=segment_id,
                vector=vector,
                file_id=file_record.id,
                modality=modality.value,
                content=segment.content,
                source_path=file_record.storage_path,
                title=file_record.filename,
                start_time=segment.start_time,
                end_time=segment.end_time,
            )
        )

    vector_store.upsert_segments(vector_segments)
    return len(vector_segments)
