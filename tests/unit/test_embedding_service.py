from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.embedding_service import EmbeddingService


@pytest.mark.unit
def test_embed_texts_batches_openai_calls():
    settings = Settings(openai_api_key="test-key", embedding_batch_size=2)
    service = EmbeddingService(settings)

    def make_embedding(index: int) -> list[float]:
        return [float(index), float(index + 1)]

    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(index=0, embedding=make_embedding(0)),
        MagicMock(index=1, embedding=make_embedding(1)),
    ]
    mock_response_2 = MagicMock()
    mock_response_2.data = [MagicMock(index=0, embedding=make_embedding(2))]

    with patch.object(service._client.embeddings, "create", side_effect=[mock_response, mock_response_2]) as create:
        vectors = service.embed_texts(["a", "b", "c"])

    assert create.call_count == 2
    assert len(vectors) == 3
    assert vectors[0] == [0.0, 1.0]
    assert vectors[2] == [2.0, 3.0]


@pytest.mark.unit
def test_embed_texts_returns_empty_for_no_input():
    settings = Settings(openai_api_key="test-key")
    service = EmbeddingService(settings)
    assert service.embed_texts([]) == []
