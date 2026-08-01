"""V5 Phase 0 (M0.2): retrieval quality baseline against the golden dataset.

Requires a real Postgres + Qdrant + OpenAI-backed environment seeded via
`backend/scripts/seed_eval_corpus.py`. Excluded from the default unit run —
invoke explicitly with `pytest tests/evals -m evals`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.evals.retrieval_metrics import evaluate_retrieval, load_golden_dataset
from app.models.file import File
from app.models.project import Project
from app.services.embedding_service import EmbeddingService
from app.services.v2.rrf_retriever import RrfRetriever
from app.services.vector_store import VectorStore
from app.services.v5.reranker import Reranker

# Must match EVAL_PROJECT_NAME in backend/scripts/seed_eval_corpus.py.
EVAL_PROJECT_NAME = "Scrutinize Eval Corpus"

RESULTS_DIR = Path(__file__).resolve().parents[2] / "backend" / "app" / "evals" / "results"


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _doc_id_from_storage_path(storage_path: str) -> str:
    # Seeded as "eval-fixture://<doc_id>" by seed_eval_corpus.py
    prefix = "eval-fixture://"
    return storage_path[len(prefix):] if storage_path.startswith(prefix) else storage_path


@pytest.fixture(scope="module")
def eval_project_id() -> UUID:
    engine = get_engine()
    with Session(engine) as session:
        project = session.exec(
            select(Project).where(Project.name == EVAL_PROJECT_NAME)
        ).first()
        if project is None:
            pytest.skip(
                "Eval corpus not seeded — run `python backend/scripts/seed_eval_corpus.py` first."
            )
        return project.id


@pytest.fixture(scope="module")
def file_id_to_doc_id(eval_project_id: UUID) -> dict[str, str]:
    engine = get_engine()
    with Session(engine) as session:
        files = session.exec(
            select(File).where(File.project_id == eval_project_id)
        ).all()
        return {str(f.id): _doc_id_from_storage_path(f.storage_path) for f in files}


@pytest.mark.evals
def test_retrieval_baseline(eval_project_id: UUID, file_id_to_doc_id: dict[str, str]) -> None:
    settings = get_settings()
    vector_store = VectorStore(settings)
    embedding_service = EmbeddingService(settings)
    reranker = Reranker(settings)
    retriever = RrfRetriever(embedding_service, vector_store, settings, reranker=reranker)

    def retrieve_doc_ids(query: str) -> list[str]:
        result = retriever.retrieve(query, project_id=eval_project_id)
        doc_ids: list[str] = []
        for source in result.sources:
            doc_id = file_id_to_doc_id.get(str(source.file_id))
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
        return doc_ids

    queries = load_golden_dataset()
    summary = evaluate_retrieval(queries, retrieve_doc_ids, k=5)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sha = _git_sha()
    output_path = RESULTS_DIR / f"{sha}.json"
    output_path.write_text(json.dumps(summary.to_dict(), indent=2))

    print(f"\nRetrieval metrics @k={summary.k} (n={summary.n_queries}):")
    print(f"  Recall@{summary.k}: {summary.recall_at_k:.3f}")
    print(f"  MRR:        {summary.mrr:.3f}")
    print(f"  nDCG@{summary.k}:  {summary.ndcg_at_k:.3f}")
    print(f"  Abstention accuracy: {summary.abstention_accuracy:.3f}")
    print(f"  Results written to {output_path}")

    assert summary.n_queries == len(queries)
