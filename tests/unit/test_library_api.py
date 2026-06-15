from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.deps import get_cloudinary_storage, get_vector_store
from app.models.file import FileModality, FileStatus
from app.services.job_orchestrator import JobOrchestrator


class FakeCloudinaryStorage:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def delete(self, public_id: str, *, resource_type: str = "image") -> dict:
        self.deleted.append((public_id, resource_type))
        return {"result": "ok"}


@pytest.fixture
def library_client(client):
    fake_storage = FakeCloudinaryStorage()
    fake_vector_store = MagicMock()

    client.app.dependency_overrides[get_cloudinary_storage] = lambda: fake_storage
    client.app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    yield client, fake_storage, fake_vector_store
    client.app.dependency_overrides.pop(get_cloudinary_storage, None)
    client.app.dependency_overrides.pop(get_vector_store, None)


@pytest.mark.unit
def test_library_lists_files_with_segment_counts(session, library_client):
    client, _, _ = library_client
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="notes.txt",
        modality=FileModality.TEXT,
        storage_path="https://res.cloudinary.com/demo/raw/upload/v123/scrutinize/text/notes.txt",
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
    assert body["files"][0]["storage_url"].endswith("notes.txt")
    assert body["files"][0]["thumbnail_url"] is None


@pytest.mark.unit
def test_delete_library_file_removes_from_all_stores(session, library_client):
    client, fake_storage, fake_vector_store = library_client
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="clip.mp4",
        modality=FileModality.VIDEO,
        storage_path="https://res.cloudinary.com/demo/video/upload/v123/scrutinize/video/clip.mp4",
        size_bytes=2048,
    )
    orchestrator.create_segment(
        file_id=file_record.id,
        modality=FileModality.VIDEO,
        content="A scene",
    )
    orchestrator.create_job(file_id=file_record.id, stage="video_ingestion")
    orchestrator.mark_file_status(file_record.id, FileStatus.INDEXED)
    file_id = file_record.id

    response = client.delete(f"/library/{file_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == str(file_id)

    fake_vector_store.delete_by_file_id.assert_called_once_with(file_id)
    assert fake_storage.deleted == [("scrutinize/video/clip", "video")]

    session.expire_all()
    assert orchestrator.get_file(file_id) is None
    assert orchestrator.list_segments_for_file(file_id) == []
    assert orchestrator.list_jobs_for_file(file_id) == []


@pytest.mark.unit
def test_delete_library_file_returns_404_for_missing_file(library_client):
    client, _, _ = library_client
    response = client.delete(f"/library/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.unit
def test_stream_library_file_content_proxies_remote(session, library_client):
    client, _, _ = library_client
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="notes.txt",
        modality=FileModality.TEXT,
        storage_path="https://res.cloudinary.com/demo/raw/upload/v123/scrutinize/text/notes.txt",
        size_bytes=128,
    )

    def fake_stream(_url: str):
        yield b"Hello from Cloudinary"

    with patch("app.api.library.stream_remote_url", side_effect=fake_stream):
        response = client.get(f"/library/{file_record.id}/content")

    assert response.status_code == 200
    assert response.text == "Hello from Cloudinary"
    assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.unit
def test_stream_library_file_content_supports_download_disposition(session, library_client):
    client, _, _ = library_client
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="clip.mp4",
        modality=FileModality.VIDEO,
        storage_path="https://res.cloudinary.com/demo/video/upload/v123/scrutinize/video/clip.mp4",
        size_bytes=2048,
    )

    with patch("app.api.library.stream_remote_url", return_value=iter([b"video-bytes"])):
        response = client.get(f"/library/{file_record.id}/content?download=true")

    assert response.status_code == 200
    assert response.content == b"video-bytes"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-type"] == "video/mp4"


@pytest.mark.unit
def test_stream_library_file_content_returns_404_for_missing_file(library_client):
    client, _, _ = library_client
    response = client.get(f"/library/{uuid4()}/content")
    assert response.status_code == 404

