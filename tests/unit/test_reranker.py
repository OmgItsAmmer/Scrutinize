from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.services.v5.reranker import Reranker


def _source(content: str, score: float = 0.5) -> SearchSource:
    return SearchSource(
        segment_id=uuid4(),
        file_id=uuid4(),
        modality=FileModality.TEXT,
        title="doc.txt",
        content=content,
        source_path="https://example.com/doc.txt",
        score=score,
    )


@pytest.mark.unit
def test_rerank_disabled_returns_rrf_order_unchanged():
    settings = Settings(local_llm_base_url="http://llm.test", rerank_enabled=False)
    reranker = Reranker(settings)
    sources = [_source("a"), _source("b"), _source("c")]

    result = reranker.rerank("query", sources, top_k=2)

    assert result.applied is False
    assert [item.source.content for item in result.sources] == ["a", "b"]
    assert all(item.rerank_score is None for item in result.sources)


@pytest.mark.unit
def test_rerank_reorders_by_cross_encoder_score():
    settings = Settings(local_llm_base_url="http://llm.test", rerank_enabled=True, rerank_timeout_s=5.0)
    reranker = Reranker(settings)
    reranker._score = MagicMock(return_value=[0.1, 0.9, 0.5])
    sources = [_source("a"), _source("b"), _source("c")]

    result = reranker.rerank("query", sources, top_k=2)

    assert result.applied is True
    assert [item.source.content for item in result.sources] == ["b", "c"]
    assert result.sources[0].rerank_score == 0.9
    assert result.sources[0].rrf_rank == 2  # original RRF position preserved


@pytest.mark.unit
def test_rerank_fails_open_when_scoring_raises():
    settings = Settings(local_llm_base_url="http://llm.test", rerank_enabled=True)
    reranker = Reranker(settings)
    reranker._score = MagicMock(side_effect=RuntimeError("model load failed"))
    sources = [_source("a"), _source("b")]

    result = reranker.rerank("query", sources, top_k=5)

    assert result.applied is False
    assert result.error == "model load failed"
    assert [item.source.content for item in result.sources] == ["a", "b"]


@pytest.mark.unit
def test_rerank_fails_open_on_timeout():
    import time

    settings = Settings(local_llm_base_url="http://llm.test", rerank_enabled=True, rerank_timeout_s=0.05)
    reranker = Reranker(settings)
    reranker._score = MagicMock(side_effect=lambda *a, **k: time.sleep(0.5) or [1.0])
    sources = [_source("a")]

    result = reranker.rerank("query", sources, top_k=5)

    assert result.applied is False
    assert result.error == "timeout"


@pytest.mark.unit
def test_rerank_empty_sources_short_circuits():
    settings = Settings(local_llm_base_url="http://llm.test", rerank_enabled=True)
    reranker = Reranker(settings)

    result = reranker.rerank("query", [], top_k=5)

    assert result.sources == []
    assert result.applied is False
