from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.services.v2.rrf_retriever import RrfRetriever


@pytest.mark.unit
@pytest.mark.v2
def test_rrf_retriever_searches_rewritten_query_only():
    settings = Settings(local_llm_base_url="http://llm.test", v2_rrf_top_k=2)
    embedding = MagicMock()
    embedding.embed_texts.return_value = [[0.1]]

    id_a = str(uuid4())
    id_b = str(uuid4())
    vector_store = MagicMock()
    vector_store.search.return_value = [
        {"id": id_a, "score": 0.9, "payload": _payload("first hit")},
        {"id": id_b, "score": 0.8, "payload": _payload("second hit")},
    ]

    retriever = RrfRetriever(embedding, vector_store, settings)
    sources = retriever.retrieve("rewritten query")

    assert len(sources) == 2
    assert embedding.embed_texts.call_args.args[0] == ["rewritten query"]
    vector_store.search.assert_called_once()
    assert vector_store.search.call_args.kwargs["top_k"] == 2
    assert sources[0].score == 0.9
    assert sources[0].content == "first hit"


@pytest.mark.unit
@pytest.mark.v2
def test_rrf_retriever_returns_empty_for_blank_query():
    retriever = RrfRetriever(MagicMock(), MagicMock(), Settings(local_llm_base_url="http://llm.test"))
    assert retriever.retrieve("   ") == []


def _payload(content: str) -> dict:
    return {
        "file_id": str(uuid4()),
        "modality": FileModality.TEXT.value,
        "content": content,
        "source_path": "https://example.com/doc.txt",
        "title": "doc.txt",
    }
