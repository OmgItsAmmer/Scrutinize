from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.services.agents.router_agent import RouterResult
from app.services.search_service import SearchService


@pytest.mark.unit
def test_search_service_runs_full_pipeline():
    settings = Settings(openai_api_key="test-key", search_top_k=3)
    embedding_service = MagicMock()
    embedding_service.embed_texts.return_value = [[0.1, 0.2]]
    vector_store = MagicMock()
    segment_id = uuid4()
    file_id = uuid4()
    vector_store.search.return_value = [
        {
            "id": str(segment_id),
            "score": 0.88,
            "payload": {
                "file_id": str(file_id),
                "modality": "video",
                "title": "clip.mp4",
                "content": "Someone drinks milk",
                "source_path": "https://example.com/clip.mp4",
                "start_time": 10.0,
                "end_time": 20.0,
            },
        }
    ]
    router_agent = MagicMock()
    router_agent.route.return_value = RouterResult(
        search_query="person drinking milk",
        modality_filter=FileModality.VIDEO,
    )
    synthesis_agent = MagicMock()
    synthesis_agent.synthesize.return_value = "Try clip.mp4 at 00:10."

    service = SearchService(
        embedding_service,
        vector_store,
        router_agent,
        synthesis_agent,
        settings,
    )
    result = service.search(
        "Find the video where someone drinks milk",
        modality_filter=FileModality.VIDEO,
    )

    assert result.search_query == "person drinking milk"
    assert result.modality_filter == FileModality.VIDEO
    assert result.answer == "Try clip.mp4 at 00:10."
    assert len(result.sources) == 1
    assert result.sources[0].segment_id == segment_id
    vector_store.search.assert_called_once_with(
        [0.1, 0.2],
        top_k=3,
        modality="video",
    )
