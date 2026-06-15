from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.vector_store import VectorSegment, VectorStore


@pytest.mark.unit
def test_upsert_segments_creates_collection_when_missing():
    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = False

    segment = VectorSegment(
        id=uuid4(),
        vector=[0.1, 0.2],
        file_id=uuid4(),
        modality="text",
        content="hello",
        source_path="https://example.com/a.txt",
        title="a.txt",
        created_at=datetime.now(UTC),
    )

    store.upsert_segments([segment])

    store._client.create_collection.assert_called_once()
    store._client.upsert.assert_called_once()


@pytest.mark.unit
def test_search_applies_modality_filter():
    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = True
    store._client.search.return_value = []

    with patch.object(store, "ensure_collection"):
        store.search([0.1, 0.2], top_k=5, modality="text")

    _, kwargs = store._client.search.call_args
    assert kwargs["limit"] == 5
    assert kwargs["query_filter"] is not None
