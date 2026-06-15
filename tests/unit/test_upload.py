from unittest.mock import patch

import pytest

from app.core.deps import get_cloudinary_storage
from app.services.cloudinary_storage import StorageUploadResult
from app.services.upload_utils import detect_modality


class FakeCloudinaryStorage:
    def upload_bytes(self, data, *, filename, modality, resource_type="auto"):
        return StorageUploadResult(
            public_id=f"{modality}/{filename}",
            secure_url=f"https://res.cloudinary.com/demo/{resource_type}/upload/{filename}",
            resource_type=resource_type,
            bytes=len(data),
        )


@pytest.fixture
def upload_client(client):
    client.app.dependency_overrides[get_cloudinary_storage] = lambda: FakeCloudinaryStorage()
    yield client
    client.app.dependency_overrides.pop(get_cloudinary_storage, None)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected_modality"),
    [
        ("notes.txt", "text"),
        ("track.mp3", "audio"),
        ("clip.mp4", "video"),
    ],
)
def test_detect_modality(filename, expected_modality):
    modality = detect_modality(filename)
    assert modality is not None
    assert modality.value == expected_modality


@pytest.mark.unit
def test_upload_accepts_txt_file(upload_client):
    with patch("app.api.upload.process_text.delay") as mock_delay:
        response = upload_client.post(
            "/upload",
            files={"file": ("notes.txt", b"Hello Scrutinize text ingestion.", "text/plain")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "text"
    mock_delay.assert_called_once()


@pytest.mark.unit
def test_upload_accepts_mp3_file(upload_client):
    with patch("app.api.upload.process_audio.delay") as mock_delay:
        response = upload_client.post(
            "/upload",
            files={"file": ("track.mp3", b"fake-audio-bytes", "audio/mpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "audio"
    mock_delay.assert_called_once()


@pytest.mark.unit
def test_upload_accepts_mp4_file(upload_client):
    with patch("app.api.upload.process_video.delay") as mock_delay:
        response = upload_client.post(
            "/upload",
            files={"file": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "video"
    mock_delay.assert_called_once()


@pytest.mark.unit
def test_upload_rejects_unknown_extension(upload_client):
    response = upload_client.post(
        "/upload",
        files={"file": ("archive.zip", b"fake", "application/zip")},
    )
    assert response.status_code == 415


@pytest.mark.unit
def test_upload_rejects_empty_file(upload_client):
    response = upload_client.post(
        "/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
