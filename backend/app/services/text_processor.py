import logging
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import tiktoken

_NULL_UUID = UUID(int=0)  # Sentinel for files without a project_id (pre-multi-tenant legacy data)


from app.core.config import Settings
from app.models.file import FileModality, FileStatus
from app.models.processing_job import JobStatus
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.media_utils import resolve_media_source
from app.services.qdrant_errors import describe_worker_error
from app.services.vector_store import VectorSegment, VectorStore
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".pdf"}
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
        vision_service: VisionService | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings
        self._vision_service = vision_service

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
            is_pdf = file_record.filename.lower().endswith(".pdf")
            if is_pdf:
                logger.info("Job %s: processing PDF file %s", job_id, file_record.filename)
                temp_pdf = resolve_media_source(file_record.storage_path, suffix=".pdf")
                owns_temp_file = file_record.storage_path.startswith(("http://", "https://"))
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(temp_pdf)
                    pages_text = []
                    for page in reader.pages:
                        pages_text.append(page.extract_text() or "")
                    raw_text = "\n\n".join(pages_text)

                    chunks = chunk_text(
                        raw_text,
                        chunk_size=self._settings.text_chunk_size,
                        overlap=self._settings.text_chunk_overlap,
                    )

                    captions = []
                    with tempfile.TemporaryDirectory() as img_temp_dir:
                        img_temp_path = Path(img_temp_dir)
                        image_paths = []
                        for page_idx, page in enumerate(reader.pages):
                            for img_idx, img in enumerate(page.images):
                                suffix = Path(img.name).suffix or ".png"
                                if suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                                    suffix = ".png"
                                img_path = img_temp_path / f"page_{page_idx}_img_{img_idx}{suffix}"
                                img_path.write_bytes(img.data)
                                image_paths.append(img_path)

                        if image_paths:
                            if not self._vision_service:
                                raise RuntimeError("VisionService is not configured but PDF contains images to caption.")
                            logger.info("Job %s: extracting and captioning %d image(s)", job_id, len(image_paths))
                            captions = self._vision_service.caption_images(image_paths)

                    formatted_captions = [f"[Image]: {caption}" for caption in captions]
                    all_chunks = chunks + formatted_captions
                finally:
                    if temp_pdf is not None and owns_temp_file:
                        temp_pdf.unlink(missing_ok=True)
            else:
                logger.info("Job %s: fetching text %s", job_id, file_record.filename)
                raw_text = self._fetch_text(file_record.storage_path, file_record.filename)
                all_chunks = chunk_text(
                    raw_text,
                    chunk_size=self._settings.text_chunk_size,
                    overlap=self._settings.text_chunk_overlap,
                )

            if not all_chunks:
                raise ValueError("Text/PDF file has no text content or images after parsing")

            logger.info("Job %s: embedding %d chunk(s)", job_id, len(all_chunks))
            vectors = self._embedding_service.embed_texts(all_chunks)
            vector_segments: list[VectorSegment] = []

            for chunk, vector in zip(all_chunks, vectors, strict=True):
                segment_id = uuid4()
                self._orchestrator.create_segment(
                    file_id=file_record.id,
                    modality=FileModality.TEXT,
                    content=chunk,
                    segment_id=segment_id,
                    project_id=file_record.project_id,
                )
                vector_segments.append(
                    VectorSegment(
                        id=segment_id,
                        vector=vector,
                        file_id=file_record.id,
                        project_id=file_record.project_id or _NULL_UUID,
                        modality=FileModality.TEXT.value,
                        content=chunk,
                        source_path=file_record.storage_path,
                        title=file_record.filename,
                    )
                )

            logger.info(
                "Job %s: upserting %d segment(s) to Qdrant at %s",
                job_id,
                len(vector_segments),
                self._settings.qdrant_url,
            )
            self._vector_store.upsert_segments(vector_segments)
            self._orchestrator.update_job_status(job_id, JobStatus.DONE)
            self._orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)
            return len(vector_segments)
        except Exception as exc:
            error_message = describe_worker_error(exc)
            logger.exception("Job %s failed: %s", job_id, error_message)
            self._orchestrator.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=error_message,
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
