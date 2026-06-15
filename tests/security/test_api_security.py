import pytest


@pytest.mark.security
def test_health_response_does_not_leak_secrets(client):
    response = client.get("/health")
    body = response.text.lower()
    for secret_marker in (
        "openai_api_key",
        "cloudinary_api_secret",
        "cloudinary_api_key",
        "database_url",
        "password",
        "secret",
    ):
        assert secret_marker not in body


@pytest.mark.security
def test_unknown_job_status_does_not_expose_internals(client):
    from uuid import uuid4

    response = client.get(f"/status/{uuid4()}")
    assert response.status_code == 404
    assert "traceback" not in response.text.lower()
