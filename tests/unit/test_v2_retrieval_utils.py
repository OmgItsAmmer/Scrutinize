import pytest

from app.services.v2.retrieval_utils import fuse_rrf_hits


@pytest.mark.unit
@pytest.mark.v2
def test_fuse_rrf_prefers_documents_in_both_lists():
    dense = [{"id": "a", "score": 0.9, "payload": {}}, {"id": "b", "score": 0.8, "payload": {}}]
    sparse = [{"id": "b", "score": 0.95, "payload": {}}, {"id": "c", "score": 0.7, "payload": {}}]

    fused, stats = fuse_rrf_hits(dense, sparse, k=60, top_k=3, sparse_query_dimensions=4)

    assert stats.semantic_prefetch_count == 2
    assert stats.keyword_prefetch_count == 2
    assert stats.qdrant_retrieved_count == 3
    assert stats.rrf_both_lists == 1
    assert stats.rrf_semantic_only == 1
    assert stats.rrf_keyword_only == 1
    assert [hit["id"] for hit in fused] == ["b", "a", "c"]
    assert fused[0]["semantic_rank"] == 2
    assert fused[0]["keyword_rank"] == 1


@pytest.mark.unit
@pytest.mark.v2
def test_fuse_rrf_empty_lists():
    fused, stats = fuse_rrf_hits([], [], k=60, top_k=5)

    assert fused == []
    assert stats.semantic_prefetch_count == 0
    assert stats.keyword_prefetch_count == 0
    assert stats.qdrant_retrieved_count == 0
