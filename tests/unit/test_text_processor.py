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

    settings = Settings(openai_api_key="test-key")
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
    vision_service.caption_images.return_value = ["Caption of Image 1", "Caption of Image 2"]

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

    assert count == 3
    
    called_args = embedding_service.embed_texts.call_args[0][0]
    assert "This is page 1 text." in called_args[0]
    assert called_args[1] == "[Image]: Caption of Image 1"
    assert called_args[2] == "[Image]: Caption of Image 2"

    vision_service.caption_images.assert_called_once()
    vector_store.upsert_segments.assert_called_once()
