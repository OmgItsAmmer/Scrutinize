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
        project_id=uuid4(),
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
    store._client.query_points.return_value = MagicMock(points=[])

    with patch.object(store, "ensure_collection"):
        store.search([0.1, 0.2], project_id=uuid4(), top_k=5, modality="text")

    _, kwargs = store._client.query_points.call_args
    assert kwargs["limit"] == 5
    assert kwargs["using"] == VectorStore.TEXT_VECTOR_NAME
    assert kwargs["query_filter"] is not None


@pytest.mark.unit
def test_search_hybrid_uses_prefetch_limit_for_branches_but_top_k_for_fusion():
    from qdrant_client.models import SparseVector

    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = True
    store._client.query_points.return_value = MagicMock(points=[])

    with patch.object(store, "ensure_collection"):
        result = store.search_hybrid(
            [0.1, 0.2],
            project_id=uuid4(),
            top_k=5,
            prefetch_limit=50,
            query_sparse_vector=SparseVector(indices=[1], values=[0.5]),
        )

    assert store._client.query_points.call_count == 2
    for call in store._client.query_points.call_args_list:
        assert call.kwargs["limit"] == 50
    assert result.stats.prefetch_limit == 50


@pytest.mark.unit
def test_search_hybrid_defaults_prefetch_limit_to_top_k_when_unset():
    from qdrant_client.models import SparseVector

    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = True
    store._client.query_points.return_value = MagicMock(points=[])

    with patch.object(store, "ensure_collection"):
        store.search_hybrid(
            [0.1, 0.2],
            project_id=uuid4(),
            top_k=5,
            query_sparse_vector=SparseVector(indices=[1], values=[0.5]),
        )

    for call in store._client.query_points.call_args_list:
        assert call.kwargs["limit"] == 5


@pytest.mark.unit
def test_delete_by_file_id_uses_filter_selector():
    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = True
    file_id = uuid4()

    store.delete_by_file_id(file_id)

    assert store._client.create_payload_index.call_count == 4  # file_id, modality, project_id, conversation_id
    store._client.delete.assert_called_once()
    _, kwargs = store._client.delete.call_args
    assert kwargs["collection_name"] == "segments-test"
    assert kwargs["points_selector"].filter is not None


@pytest.mark.unit
def test_delete_by_ids_deletes_specific_points_for_reindex_swap():
    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()
    store._client.collection_exists.return_value = True
    point_ids = [uuid4(), uuid4()]

    store.delete_by_ids(point_ids)

    store._client.delete.assert_called_once()
    _, kwargs = store._client.delete.call_args
    assert kwargs["collection_name"] == "segments-test"
    assert kwargs["points_selector"] == [str(pid) for pid in point_ids]


@pytest.mark.unit
def test_delete_by_ids_noop_for_empty_list():
    settings = Settings(qdrant_collection="segments-test")
    store = VectorStore(settings)
    store._client = MagicMock()

    store.delete_by_ids([])

    store._client.delete.assert_not_called()
