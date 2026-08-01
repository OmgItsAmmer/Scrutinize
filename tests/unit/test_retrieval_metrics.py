import pytest

from app.evals.retrieval_metrics import (
    GoldenQuery,
    evaluate_retrieval,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


@pytest.mark.unit
def test_recall_at_k_partial_match():
    assert recall_at_k(["a", "b", "c"], ["a", "z"], k=3) == 0.5


@pytest.mark.unit
def test_recall_at_k_respects_k_cutoff():
    assert recall_at_k(["z", "z", "z", "a"], ["a"], k=3) == 0.0


@pytest.mark.unit
def test_recall_at_k_abstention_query_with_no_hits_scores_full():
    assert recall_at_k([], [], k=5) == 1.0


@pytest.mark.unit
def test_recall_at_k_abstention_query_with_hits_scores_zero():
    assert recall_at_k(["a"], [], k=5) == 0.0


@pytest.mark.unit
def test_reciprocal_rank_finds_first_match():
    assert reciprocal_rank(["x", "a", "b"], ["a"]) == pytest.approx(0.5)


@pytest.mark.unit
def test_reciprocal_rank_no_match_is_zero():
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


@pytest.mark.unit
def test_ndcg_perfect_ranking_is_one():
    assert ndcg_at_k(["a", "b"], ["a", "b"], k=2) == pytest.approx(1.0)


@pytest.mark.unit
def test_ndcg_relevant_doc_ranked_lower_scores_less_than_one():
    score = ndcg_at_k(["x", "a"], ["a"], k=2)
    assert 0 < score < 1.0


@pytest.mark.unit
def test_evaluate_retrieval_aggregates_and_tracks_abstention():
    queries = [
        GoldenQuery(query="q1", expected_doc_ids=["doc_a"]),
        GoldenQuery(query="q2", expected_doc_ids=[]),
    ]

    def retrieve_fn(query: str) -> list[str]:
        return ["doc_a"] if query == "q1" else []

    summary = evaluate_retrieval(queries, retrieve_fn, k=5)

    assert summary.n_queries == 2
    assert summary.recall_at_k == 1.0
    assert summary.mrr == 0.5
    assert summary.abstention_accuracy == 1.0
