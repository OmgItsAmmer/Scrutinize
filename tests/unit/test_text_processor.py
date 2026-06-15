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
    ],
)
def test_is_text_filename(filename: str, expected: bool):
    assert is_text_filename(filename) is expected
