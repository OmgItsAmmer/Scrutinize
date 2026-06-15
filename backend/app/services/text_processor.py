from pathlib import Path
from uuid import UUID, uuid4

import tiktoken

from app.core.config import Settings
from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.media_utils import resolve_media_source
from app.services.vector_store import VectorSegment, VectorStore

TEXT_EXTENSIONS = {".txt", ".md"}
TEXT_STAGE = "text_ingestion"


def chunk_text(
    text: str,
    *,
    chunk_size: int = 400,
    overlap: int = 50,
    encoding_name: str = "cl100k_base",
) -> list[str]:
    """Split text into token windows with overlap (tiktoken-aware)."""
    stripped = text.strip()
    if not stripped:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(stripped)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(encoding.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end - overlap
    return chunks


def is_text_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in TEXT_EXTENSIONS


class TextProcessor:
    """Text chunking + embedding pipeline (M2)."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings

    def process(self, job_id: UUID) -> int:
        job = self._orchestrator.get_job(job_id)
        if job is None:
            raise LookupError(f"Processing job {job_id} not found")

        file_record = self._orchestrator.get_file(job.file_id)
        if file_record is None:
            raise LookupError(f"File {job.file_id} not found")

        if file_record.modality != FileModality.TEXT:
            raise ValueError(f"File {file_record.id} is not a text file")

        self._orchestrator.update_job_status(job_id, JobStatus.RUNNING)
        self._orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

        try:
            raw_text = self._fetch_text(file_record.storage_path, file_record.filename)
            chunks = chunk_text(
                raw_text,
                chunk_size=self._settings.text_chunk_size,
                overlap=self._settings.text_chunk_overlap,
            )
            if not chunks:
                raise ValueError("Text file is empty after trimming")

            vectors = self._embedding_service.embed_texts(chunks)
            vector_segments: list[VectorSegment] = []

            for chunk, vector in zip(chunks, vectors, strict=True):
                segment_id = uuid4()
                self._orchestrator.create_segment(
                    file_id=file_record.id,
                    modality=FileModality.TEXT,
                    content=chunk,
                    segment_id=segment_id,
                )
                vector_segments.append(
                    VectorSegment(
                        id=segment_id,
                        vector=vector,
                        file_id=file_record.id,
                        modality=FileModality.TEXT.value,
                        content=chunk,
                        source_path=file_record.storage_path,
                        title=file_record.filename,
                    )
                )

            self._vector_store.upsert_segments(vector_segments)
            self._orchestrator.update_job_status(job_id, JobStatus.DONE)
            self._orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)
            return len(vector_segments)
        except Exception as exc:
            self._orchestrator.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=str(exc),
            )
            self._orchestrator.mark_file_status(file_record.id, FileStatus.FAILED)
            raise

    def _fetch_text(self, source: str, filename: str) -> str:
        suffix = Path(filename).suffix or ".txt"
        path = resolve_media_source(source, suffix=suffix)
        if path.is_file() and not source.startswith(("http://", "https://")):
            return path.read_text(encoding="utf-8")

        import httpx

        response = httpx.get(source, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text
