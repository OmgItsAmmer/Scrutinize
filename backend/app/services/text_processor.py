import logging
from concurrent.futures import ThreadPoolExecutor
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
from app.services.parsing.base import ContentBlock, ParsedDocument
from app.services.parsing.chunking import Chunk, chunk_blocks
from app.services.parsing.factory import get_document_parser
from app.services.qdrant_errors import describe_worker_error
from app.services.v5.context_enricher import ContextEnricher
from app.services.vector_store import VectorSegment, VectorStore
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".pdf"}
TEXT_STAGE = "text_ingestion"

SCANNED_PDF_ERROR = (
    "This PDF appears to be a scanned image and text could not be extracted, "
    "even after attempting OCR."
)


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
    """Text/PDF chunking + embedding pipeline. Structured parsing via Docling (V5 M3/M4)."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        settings: Settings,
        vision_service: VisionService | None = None,
        context_enricher: ContextEnricher | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._settings = settings
        self._vision_service = vision_service
        self._context_enricher = context_enricher

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
                logger.info("Job %s: parsing PDF file %s", job_id, file_record.filename)
                temp_pdf = resolve_media_source(file_record.storage_path, suffix=".pdf")
                owns_temp_file = file_record.storage_path.startswith(("http://", "https://"))
                try:
                    parser = get_document_parser(self._settings, vision_service=self._vision_service)
                    parsed = parser.parse(temp_pdf)
                finally:
                    if temp_pdf is not None and owns_temp_file:
                        temp_pdf.unlink(missing_ok=True)

                if parsed.is_scanned and not parsed.blocks:
                    # Density check tripped and OCR (Docling's built-in pass, or the
                    # pypdf-path fallback in ocr.py) still produced nothing usable.
                    raise ValueError(SCANNED_PDF_ERROR)

                blocks = parsed.blocks
            else:
                logger.info("Job %s: fetching text %s", job_id, file_record.filename)
                raw_text = self._fetch_text(file_record.storage_path, file_record.filename)
                blocks = [
                    ContentBlock(text=raw_text, page_number=None, section_path=None, block_type="paragraph")
                ] if raw_text.strip() else []

            chunks = chunk_blocks(
                blocks,
                chunk_size=self._settings.text_chunk_size,
                overlap=self._settings.text_chunk_overlap,
            )

            if not chunks:
                raise ValueError("Text/PDF file has no text content or images after parsing")

            context_headers: list[str] = [""] * len(chunks)
            if self._context_enricher and self._settings.contextual_retrieval_enabled:
                document_text = "\n\n".join(b.text for b in blocks)
                logger.info("Job %s: generating context headers for %d chunk(s)", job_id, len(chunks))

                def _enrich_chunk(item: tuple[int, Chunk]) -> tuple[int, str]:
                    index, chunk = item
                    enriched = self._context_enricher.enrich(
                        document_text=document_text,
                        chunk_text=chunk.text,
                        title=file_record.filename,
                        section_path=chunk.section_path,
                    )
                    return index, enriched.context_header

                # I/O-bound LLM calls — run concurrently instead of one chunk at a
                # time, otherwise a 100-chunk document serializes 100 network round
                # trips (~1-1.5 min+) purely on this stage.
                max_workers = max(1, min(self._settings.context_enrichment_max_workers, len(chunks)))
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    for index, header in pool.map(_enrich_chunk, enumerate(chunks)):
                        context_headers[index] = header

            logger.info("Job %s: embedding %d chunk(s)", job_id, len(chunks))
            embed_texts = [
                f"{header}\n\n{chunk.text}" if header else chunk.text
                for header, chunk in zip(context_headers, chunks, strict=True)
            ]
            vectors = self._embedding_service.embed_texts(embed_texts)
            vector_segments: list[VectorSegment] = []

            for chunk, vector, header in zip(chunks, vectors, context_headers, strict=True):
                segment_id = uuid4()
                self._orchestrator.create_segment(
                    file_id=file_record.id,
                    modality=FileModality.TEXT,
                    content=chunk.text,
                    segment_id=segment_id,
                    project_id=file_record.project_id,
                    page_number=chunk.page_number,
                    section_path=chunk.section_path,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    block_type=chunk.block_type,
                    context_header=header or None,
                    pipeline_version=self._settings.text_pipeline_version,
                )
                vector_segments.append(
                    VectorSegment(
                        id=segment_id,
                        vector=vector,
                        file_id=file_record.id,
                        project_id=file_record.project_id or _NULL_UUID,
                        modality=FileModality.TEXT.value,
                        content=chunk.text,
                        source_path=file_record.storage_path,
                        title=file_record.filename,
                        page_number=chunk.page_number,
                        section_path=chunk.section_path,
                        block_type=chunk.block_type,
                        context_header=header or None,
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
