from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.deps import get_search_service
from app.models.file import FileModality
from app.schemas.search import SearchResponse, SearchSource


@pytest.mark.unit
def test_search_endpoint_returns_response(client):
    source = SearchSource(
        segment_id=uuid4(),
        file_id=uuid4(),
        modality=FileModality.TEXT,
        title="notes.txt",
        content="Project plan details",
        source_path="https://example.com/notes.txt",
        score=0.75,
    )
    mock_service = MagicMock()
    mock_service.search.return_value = SearchResponse(
        query="What does the plan say?",
        search_query="project plan details",
        modality_filter=None,
        answer="The plan covers ingestion and search.",
        sources=[source],
    )
    client.app.dependency_overrides[get_search_service] = lambda: mock_service

    response = client.post(
        "/search",
        json={"query": "What does the plan say?"},
    )

    client.app.dependency_overrides.pop(get_search_service, None)
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The plan covers ingestion and search."
    assert body["sources"][0]["modality"] == "text"
    mock_service.search.assert_called_once()


@pytest.mark.unit
def test_search_endpoint_rejects_empty_query(client):
    response = client.post("/search", json={"query": ""})
    assert response.status_code == 422
