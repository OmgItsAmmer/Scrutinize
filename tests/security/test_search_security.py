from unittest.mock import MagicMock

import pytest

from app.core.deps import get_search_service
from app.schemas.search import SearchResponse


@pytest.mark.security
def test_search_response_does_not_leak_secrets(client):
    mock_service = MagicMock()
    mock_service.search.return_value = SearchResponse(
        query="test",
        search_query="test",
        answer="ok",
        sources=[],
    )
    client.app.dependency_overrides[get_search_service] = lambda: mock_service

    response = client.post("/search", json={"query": "hello"})
    client.app.dependency_overrides.pop(get_search_service, None)

    body = response.text.lower()
    for secret_marker in (
        "openai_api_key",
        "cloudinary_api_secret",
        "database_url",
        "password",
    ):
        assert secret_marker not in body


@pytest.mark.security
def test_search_validation_error_does_not_expose_traceback(client):
    response = client.post("/search", json={"query": ""})
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()
