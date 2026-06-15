import pytest

from app.models.file import FileModality, FileStatus
from app.services.job_orchestrator import JobOrchestrator


@pytest.mark.unit
def test_library_lists_files_with_segment_counts(session, client):
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="notes.txt",
        modality=FileModality.TEXT,
        storage_path="https://example.com/notes.txt",
        size_bytes=128,
    )
    orchestrator.create_segment(
        file_id=file_record.id,
        modality=FileModality.TEXT,
        content="Hello world",
    )
    orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)

    response = client.get("/library")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["files"][0]["filename"] == "notes.txt"
    assert body["files"][0]["segment_count"] == 1
    assert body["files"][0]["status"] == "indexed"
