from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.services.v2.retrieval_utils import RetrievalStats
from app.services.v2.rrf_retriever import RrfRetriever


@pytest.mark.unit
@pytest.mark.v2
@patch("app.services.v2.rrf_retriever.embed_sparse_query")
def test_rrf_retriever_searches_rewritten_query_only(mock_embed_sparse):
    settings = Settings(local_llm_base_url="http://llm.test", v2_rrf_top_k=2, v2_rrf_k=60)
    embedding = MagicMock()
    embedding.embed_texts.return_value = [[0.1]]

    id_a = str(uuid4())
    id_b = str(uuid4())
    vector_store = MagicMock()
    mock_embed_sparse.return_value = MagicMock(indices=[1, 2], values=[0.5, 0.8])
    stats = RetrievalStats(
        semantic_prefetch_count=2,
        keyword_prefetch_count=2,
        qdrant_retrieved_count=2,
        rrf_k=60,
        rrf_semantic_only=0,
        rrf_keyword_only=0,
        rrf_both_lists=2,
        sparse_query_dimensions=2,
    )
    vector_store.search_hybrid.return_value = MagicMock(
        hits=[
            {
                "id": id_a,
                "score": 0.032,
                "payload": _payload("first hit"),
                "semantic_rank": 1,
                "keyword_rank": 2,
            },
            {
                "id": id_b,
                "score": 0.031,
                "payload": _payload("second hit"),
                "semantic_rank": 2,
                "keyword_rank": 1,
            },
        ],
        stats=stats,
    )

    retriever = RrfRetriever(embedding, vector_store, settings)
    project_id = uuid4()
    result = retriever.retrieve("rewritten query", project_id=project_id)

    assert len(result.sources) == 2
    assert embedding.embed_texts.call_args.args[0] == ["rewritten query"]
    mock_embed_sparse.assert_called_once_with(vector_store.sparse_model, "rewritten query")
    vector_store.search_hybrid.assert_called_once()
    assert vector_store.search_hybrid.call_args.kwargs["top_k"] == 2
    assert vector_store.search_hybrid.call_args.kwargs["project_id"] == project_id
    assert vector_store.search_hybrid.call_args.kwargs["rrf_k"] == 60
    assert result.sources[0].score == 0.032
    assert result.sources[0].content == "first hit"
    assert result.stats.keyword_prefetch_count == 2
    assert result.source_rank_fields[0]["semantic_rank"] == 1
    assert result.source_rank_fields[0]["keyword_rank"] == 2


@pytest.mark.unit
@pytest.mark.v2
def test_rrf_retriever_returns_empty_for_blank_query():
    retriever = RrfRetriever(MagicMock(), MagicMock(), Settings(local_llm_base_url="http://llm.test"))
    result = retriever.retrieve("   ", project_id=uuid4())
    assert result.sources == []
    assert result.stats.qdrant_retrieved_count == 0


def _payload(content: str) -> dict:
    return {
        "file_id": str(uuid4()),
        "modality": FileModality.TEXT.value,
        "content": content,
        "source_path": "https://example.com/doc.txt",
        "title": "doc.txt",
    }
