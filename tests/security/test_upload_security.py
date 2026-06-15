from unittest.mock import patch

import pytest

from app.core.deps import get_app_settings, get_cloudinary_storage
from app.core.config import Settings
from app.services.cloudinary_storage import StorageUploadResult


class FakeCloudinaryStorage:
    def upload_bytes(self, data, *, filename, modality, resource_type="auto"):
        return StorageUploadResult(
            public_id=f"{modality}/{filename}",
            secure_url=f"https://res.cloudinary.com/demo/raw/upload/{filename}",
            resource_type="raw",
            bytes=len(data),
        )


@pytest.fixture
def secured_upload_client(client):
    client.app.dependency_overrides[get_cloudinary_storage] = lambda: FakeCloudinaryStorage()
    yield client
    client.app.dependency_overrides.pop(get_cloudinary_storage, None)


@pytest.mark.security
def test_upload_rejects_unsupported_binary_extension(secured_upload_client):
    response = secured_upload_client.post(
        "/upload",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 415


@pytest.mark.security
def test_upload_rejects_path_traversal_filename(secured_upload_client):
    response = secured_upload_client.post(
        "/upload",
        files={"file": ("../../etc/passwd.txt", b"secret", "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.security
def test_upload_rejects_oversized_payload(secured_upload_client):
    tiny_settings = Settings(max_upload_bytes=16, openai_api_key="test")
    secured_upload_client.app.dependency_overrides[get_app_settings] = lambda: tiny_settings

    response = secured_upload_client.post(
        "/upload",
        files={"file": ("big.txt", b"x" * 32, "text/plain")},
    )
    assert response.status_code == 413
    secured_upload_client.app.dependency_overrides.pop(get_app_settings, None)


@pytest.mark.security
def test_upload_rejects_invalid_utf8(secured_upload_client):
    response = secured_upload_client.post(
        "/upload",
        files={"file": ("bad.txt", b"\xff\xfe", "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.security
def test_upload_does_not_echo_file_contents(secured_upload_client):
    secret = b"super-secret-content"
    with patch("app.api.upload.process_text.delay"):
        response = secured_upload_client.post(
            "/upload",
            files={"file": ("secret.txt", secret, "text/plain")},
        )

    assert response.status_code == 200
    assert secret.decode() not in response.text
