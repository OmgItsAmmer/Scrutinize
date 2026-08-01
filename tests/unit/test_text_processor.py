import pytest

from app.services.text_processor import chunk_text, is_text_filename


@pytest.mark.unit
def test_chunk_text_returns_empty_for_blank_input():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


@pytest.mark.unit
def test_chunk_text_single_short_document():
    text = "Hello from Scrutinize."
    chunks = chunk_text(text, chunk_size=50, overlap=5)
    assert len(chunks) == 1
    assert "Scrutinize" in chunks[0]


@pytest.mark.unit
def test_chunk_text_splits_long_document_with_overlap():
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


@pytest.mark.unit
def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("hello", chunk_size=10, overlap=10)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("notes.txt", True),
        ("README.md", True),
        ("song.mp3", False),
        ("../etc/passwd.txt", True),
        ("document.pdf", True),
    ],
)
def test_is_text_filename(filename: str, expected: bool):
    assert is_text_filename(filename) is expected


@pytest.mark.unit
def test_text_processor_pdf_ingestion(session):
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from app.models.file import FileModality
    from app.core.config import Settings
    from app.services.job_orchestrator import JobOrchestrator
    from app.services.text_processor import TextProcessor

    settings = Settings(openai_api_key="test-key", parser_backend="pypdf", ocr_enabled=False)
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="test_doc.pdf",
        modality=FileModality.TEXT,
        storage_path="https://example.com/test_doc.pdf",
        size_bytes=1000,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="text_ingestion")

    embedding_service = MagicMock()
    embedding_service.embed_texts.side_effect = lambda texts: [[0.1] * 1536 for _ in texts]
    
    vector_store = MagicMock()
    vision_service = MagicMock()
    # Real VisionService.caption_images returns one caption per image path passed in;
    # the pipeline now calls it once per page, so the mock must do the same.
    vision_service.caption_images.side_effect = lambda paths: [
        f"Caption of Image {i + 1}" for i in range(len(paths))
    ]

    processor = TextProcessor(
        orchestrator,
        embedding_service,
        vector_store,
        settings,
        vision_service=vision_service,
    )

    class FakeImage:
        def __init__(self, name: str, data: bytes):
            self.name = name
            self.data = data

    class FakePage:
        def __init__(self, text: str, images: list[FakeImage]):
            self._text = text
            self.images = images
        
        def extract_text(self) -> str:
            return self._text

    class FakePdfReader:
        def __init__(self, stream_or_path):
            self.pages = [
                FakePage("This is page 1 text.", [FakeImage("image1.png", b"fakeimg1")]),
                FakePage("This is page 2 text.", [FakeImage("image2.jpg", b"fakeimg2")]),
            ]

    with (
        patch("app.services.text_processor.resolve_media_source", return_value=Path("fake.pdf")),
        patch("pypdf.PdfReader", FakePdfReader),
        patch.object(Path, "unlink", return_value=None),
    ):
        count = processor.process(job.id)

    assert count == 4

    called_args = embedding_service.embed_texts.call_args[0][0]
    assert "This is page 1 text." in called_args[0]
    assert called_args[1] == "[Image]: Caption of Image 1"
    assert "This is page 2 text." in called_args[2]
    assert called_args[3] == "[Image]: Caption of Image 1"

    assert vision_service.caption_images.call_count == 2  # one call per page
    vector_store.upsert_segments.assert_called_once()


@pytest.mark.unit
def test_text_processor_reports_scanned_pdf_with_specific_message(session):
    from pathlib import Path
    from unittest.mock import MagicMock, patch
    from app.models.file import FileModality, FileStatus
    from app.core.config import Settings
    from app.services.job_orchestrator import JobOrchestrator
    from app.services.text_processor import TextProcessor, SCANNED_PDF_ERROR

    settings = Settings(openai_api_key="test-key", parser_backend="pypdf", ocr_enabled=True)
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="scanned.pdf",
        modality=FileModality.TEXT,
        storage_path="https://example.com/scanned.pdf",
        size_bytes=1000,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="text_ingestion")

    embedding_service = MagicMock()
    vector_store = MagicMock()
    processor = TextProcessor(orchestrator, embedding_service, vector_store, settings)

    class FakePage:
        images: list = []

        def extract_text(self) -> str:
            return ""

    class FakePdfReader:
        def __init__(self, stream_or_path):
            self.pages = [FakePage(), FakePage()]

    with (
        patch("app.services.text_processor.resolve_media_source", return_value=Path("fake.pdf")),
        patch("pypdf.PdfReader", FakePdfReader),
        patch("app.services.parsing.ocr.ocr_pdf_pages", return_value=[]),
        patch.object(Path, "unlink", return_value=None),
    ):
        with pytest.raises(ValueError, match="scanned image"):
            processor.process(job.id)

    updated_file = orchestrator.get_file(file_record.id)
    assert updated_file.status == FileStatus.FAILED

    jobs = orchestrator.list_jobs_for_file(file_record.id)
    assert jobs[0].error_message == SCANNED_PDF_ERROR


@pytest.mark.unit
def test_text_processor_embeds_context_header_but_keeps_content_clean(session):
    from unittest.mock import MagicMock, patch
    from app.models.file import FileModality
    from app.core.config import Settings
    from app.services.job_orchestrator import JobOrchestrator
    from app.services.text_processor import TextProcessor
    from app.services.v5.context_enricher import EnrichedChunk

    settings = Settings(openai_api_key="test-key", contextual_retrieval_enabled=True)
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="notes.txt",
        modality=FileModality.TEXT,
        storage_path="https://example.com/notes.txt",
        size_bytes=100,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="text_ingestion")

    embedding_service = MagicMock()
    embedding_service.embed_texts.side_effect = lambda texts: [[0.1] * 1536 for _ in texts]
    vector_store = MagicMock()

    context_enricher = MagicMock()
    context_enricher.enrich.return_value = EnrichedChunk(
        context_header="Notes about the quarterly roadmap.",
        used_llm=True,
    )

    processor = TextProcessor(
        orchestrator,
        embedding_service,
        vector_store,
        settings,
        context_enricher=context_enricher,
    )

    with patch(
        "app.services.text_processor.TextProcessor._fetch_text",
        return_value="The roadmap covers Q1 and Q2 milestones.",
    ):
        count = processor.process(job.id)

    assert count == 1

    embedded_text = embedding_service.embed_texts.call_args[0][0][0]
    assert embedded_text.startswith("Notes about the quarterly roadmap.")
    assert "The roadmap covers Q1 and Q2 milestones." in embedded_text

    segments = orchestrator.list_segments_for_file(file_record.id)
    assert len(segments) == 1
    # DB/citation content stays clean — no generated header mixed in.
    assert segments[0].content == "The roadmap covers Q1 and Q2 milestones."
    assert segments[0].context_header == "Notes about the quarterly roadmap."
    assert segments[0].pipeline_version == settings.text_pipeline_version

    vector_segment = vector_store.upsert_segments.call_args[0][0][0]
    assert vector_segment.content == "The roadmap covers Q1 and Q2 milestones."
    assert vector_segment.context_header == "Notes about the quarterly roadmap."
