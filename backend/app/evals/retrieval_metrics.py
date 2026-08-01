"""Retrieval quality metrics against the golden dataset (V5 Phase 0 / M0.2).

Plain functions, no eval-framework dependency — DeepEval/Ragas adoption is
deferred to Phase 7 once there are measured deltas worth packaging.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parent / "datasets" / "retrieval_golden.jsonl"
)


@dataclass(frozen=True)
class GoldenQuery:
    query: str
    expected_doc_ids: list[str]
    category: str = ""

    @property
    def is_abstention(self) -> bool:
        """No supporting document exists in the corpus for this query."""
        return not self.expected_doc_ids


def load_golden_dataset(path: Path | str = DEFAULT_DATASET_PATH) -> list[GoldenQuery]:
    entries: list[GoldenQuery] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            entries.append(
                GoldenQuery(
                    query=row["query"],
                    expected_doc_ids=list(row.get("expected_doc_ids") or []),
                    category=row.get("category", ""),
                )
            )
    return entries


def recall_at_k(retrieved_doc_ids: list[str], expected_doc_ids: list[str], k: int) -> float:
    """Fraction of expected docs present anywhere in the top-k retrieved list."""
    if not expected_doc_ids:
        return 1.0 if not retrieved_doc_ids[:k] else 0.0
    top_k = set(retrieved_doc_ids[:k])
    hits = sum(1 for doc_id in expected_doc_ids if doc_id in top_k)
    return hits / len(expected_doc_ids)


def reciprocal_rank(retrieved_doc_ids: list[str], expected_doc_ids: list[str]) -> float:
    """1/rank of the first relevant document; 0 if none found (or none expected)."""
    if not expected_doc_ids:
        return 0.0
    expected = set(expected_doc_ids)
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in expected:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_doc_ids: list[str], expected_doc_ids: list[str], k: int) -> float:
    """Binary-relevance nDCG@k (each expected doc has relevance 1)."""
    if not expected_doc_ids:
        return 1.0 if not retrieved_doc_ids[:k] else 0.0
    expected = set(expected_doc_ids)
    top_k = retrieved_doc_ids[:k]

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(top_k, start=1)
        if doc_id in expected
    )
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


@dataclass(frozen=True)
class QueryResult:
    query: GoldenQuery
    retrieved_doc_ids: list[str]
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float
    abstained: bool  # true if nothing was retrieved


@dataclass(frozen=True)
class MetricsSummary:
    k: int
    n_queries: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    abstention_accuracy: float  # of abstention-category queries, fraction with empty retrieval
    per_query: list[QueryResult]

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "n_queries": self.n_queries,
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "ndcg_at_k": self.ndcg_at_k,
            "abstention_accuracy": self.abstention_accuracy,
        }


def evaluate_retrieval(
    queries: list[GoldenQuery],
    retrieve_fn,
    *,
    k: int = 5,
) -> MetricsSummary:
    """Run `retrieve_fn(query.query) -> list[str doc_ids]` over the dataset and score it.

    `retrieve_fn` returns ranked doc_ids (or file_ids/segment_ids mapped to
    doc_ids by the caller) for a query, most relevant first.
    """
    per_query: list[QueryResult] = []
    for gq in queries:
        retrieved = retrieve_fn(gq.query)
        per_query.append(
            QueryResult(
                query=gq,
                retrieved_doc_ids=retrieved,
                recall_at_k=recall_at_k(retrieved, gq.expected_doc_ids, k),
                reciprocal_rank=reciprocal_rank(retrieved, gq.expected_doc_ids),
                ndcg_at_k=ndcg_at_k(retrieved, gq.expected_doc_ids, k),
                abstained=not retrieved,
            )
        )

    n = len(per_query) or 1
    recall = sum(r.recall_at_k for r in per_query) / n
    mrr = sum(r.reciprocal_rank for r in per_query) / n
    ndcg = sum(r.ndcg_at_k for r in per_query) / n

    abstention_queries = [r for r in per_query if r.query.is_abstention]
    abstention_accuracy = (
        sum(1 for r in abstention_queries if r.abstained) / len(abstention_queries)
        if abstention_queries
        else 0.0
    )

    return MetricsSummary(
        k=k,
        n_queries=len(per_query),
        recall_at_k=recall,
        mrr=mrr,
        ndcg_at_k=ndcg,
        abstention_accuracy=abstention_accuracy,
        per_query=per_query,
    )
