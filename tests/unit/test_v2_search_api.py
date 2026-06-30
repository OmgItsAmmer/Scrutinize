from unittest.mock import MagicMock

import pytest

from app.core.deps import get_pipeline_orchestrator
from app.schemas.v2.search import SearchV2Response, SearchV2Route
from app.services.v2.llm_clients.local import LocalLlmError


@pytest.mark.unit
@pytest.mark.v2
def test_v2_search_endpoint_generic(client):
    mock_orchestrator = MagicMock()
    mock_orchestrator.search.return_value = SearchV2Response(
        query="Hello",
        rewritten_query="hello greeting",
        route=SearchV2Route.GENERIC,
        gate_reason="Small talk",
        answer="Hi there!",
        sources=[],
        attempts=1,
        conversation={"messages": []},
    )
    client.app.dependency_overrides[get_pipeline_orchestrator] = lambda: mock_orchestrator

    response = client.post("/v2/search", json={"query": "Hello"})

    client.app.dependency_overrides.pop(get_pipeline_orchestrator, None)
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "generic"
    assert body["answer"] == "Hi there!"
    mock_orchestrator.search.assert_called_once_with(
        "Hello",
        project_ctx=None,
        modality_filter=None,
        conversation=None,
    )


@pytest.mark.unit
@pytest.mark.v2
def test_v2_search_endpoint_rag_with_sources(client):
    from uuid import uuid4

    from app.models.file import FileModality
    from app.schemas.search import SearchSource

    mock_orchestrator = MagicMock()
    mock_orchestrator.search.return_value = SearchV2Response(
        query="How much garlic?",
        rewritten_query="garlic quantity recipe",
        route=SearchV2Route.RAG,
        gate_reason="Library query",
        answer="Two cloves of garlic.",
        sources=[
            SearchSource(
                segment_id=uuid4(),
                file_id=uuid4(),
                modality=FileModality.TEXT,
                title="pasta.md",
                content="Use 2 cloves garlic.",
                source_path="https://example.com/pasta.md",
                score=0.88,
            )
        ],
        attempts=1,
        conversation={"messages": []},
    )
    client.app.dependency_overrides[get_pipeline_orchestrator] = lambda: mock_orchestrator

    response = client.post("/v2/search", json={"query": "How much garlic?"})

    client.app.dependency_overrides.pop(get_pipeline_orchestrator, None)
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "rag"
    assert len(body["sources"]) == 1
    assert "garlic" in body["answer"].lower()


@pytest.mark.unit
@pytest.mark.v2
def test_v2_search_endpoint_rejects_empty_query(client):
    response = client.post("/v2/search", json={"query": ""})
    assert response.status_code == 422


@pytest.mark.unit
@pytest.mark.v2
def test_v2_search_endpoint_llm_unavailable(client):
    mock_orchestrator = MagicMock()
    mock_orchestrator.search.side_effect = LocalLlmError("Local LLM request timed out after 120s")
    client.app.dependency_overrides[get_pipeline_orchestrator] = lambda: mock_orchestrator

    response = client.post("/v2/search", json={"query": "Hello"})

    client.app.dependency_overrides.pop(get_pipeline_orchestrator, None)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
