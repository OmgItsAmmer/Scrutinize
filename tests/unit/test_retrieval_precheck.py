import pytest

from app.core.config import Settings
from app.services.v2.retrieval_precheck import RetrievalPrecheck
from app.services.v2.retrieval_utils import RetrieveResult, RetrievalStats
from app.schemas.search import SearchSource
from uuid import uuid4


class FakeRetriever:
    def __init__(self, score: float) -> None:
        self._score = score

    def retrieve(self, *args, **kwargs) -> RetrieveResult:
        source = SearchSource(
            segment_id=uuid4(),
            file_id=uuid4(),
            modality="text",
            title="Doc",
            content="hello",
            source_path="/doc",
            score=self._score,
        )
        return RetrieveResult(
            sources=[source],
            stats=RetrievalStats.empty(rrf_k=60),
            source_rank_fields=[],
            latency_ms=1,
        )


@pytest.mark.unit
@pytest.mark.v2
def test_precheck_high_score_skips_gate():
    precheck = RetrievalPrecheck(FakeRetriever(0.03), Settings())
    result = precheck.evaluate(
        "query",
        project_id=uuid4(),
        conversation_id=uuid4(),
        has_corpus=True,
    )
    assert result.action == "route_rag"


@pytest.mark.unit
@pytest.mark.v2
def test_precheck_low_score_routes_web():
    precheck = RetrievalPrecheck(FakeRetriever(0.005), Settings())
    result = precheck.evaluate(
        "query",
        project_id=uuid4(),
        conversation_id=uuid4(),
        has_corpus=True,
    )
    assert result.action == "route_web"


@pytest.mark.unit
@pytest.mark.v2
def test_precheck_pdf_tool_routes_rag_when_corpus_exists():
    precheck = RetrievalPrecheck(FakeRetriever(0.03), Settings())
    result = precheck.evaluate(
        "generate me pdf of how to cook an omelette",
        project_id=uuid4(),
        conversation_id=uuid4(),
        has_corpus=True,
        client_requested_tool="generate_pdf",
    )
    assert result.action == "route_rag"
