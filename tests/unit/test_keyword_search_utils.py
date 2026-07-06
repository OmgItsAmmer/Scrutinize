import pytest
from qdrant_client.models import SparseVector

from app.services.keyword_search_utils import (
    build_sparse_index_text,
    embed_sparse_query,
    filename_stem,
    keyword_variants,
    merge_sparse_vectors,
    normalize_for_keyword_search,
)


@pytest.mark.unit
def test_normalize_for_keyword_search_unifies_separators():
    assert normalize_for_keyword_search("  Open-AI_API  ") == "open ai api"


@pytest.mark.unit
def test_keyword_variants_collapses_compound_terms():
    assert keyword_variants("open ai") == ["open ai", "openai"]
    assert keyword_variants("OpenAI") == ["openai"]


@pytest.mark.unit
def test_keyword_variants_iteratively_collapses_multiple_gaps():
    variants = keyword_variants("open ai api")
    assert "open ai api" in variants
    assert "openai api" in variants
    assert "openaiapi" in variants


@pytest.mark.unit
def test_filename_stem_from_url():
    assert filename_stem("https://cdn.example.com/files/OpenAI-Setup.pdf") == "openai setup"


@pytest.mark.unit
def test_build_sparse_index_text_includes_content_title_and_filename():
    text = build_sparse_index_text(
        content="Uses the OpenAI API",
        title="Open-AI Notes",
        source_path="https://example.com/open ai guide.pdf",
    )
    assert "openai api" in text
    assert "open ai" in text
    assert "openai" in text
    assert "open ai notes" in text
    assert "open ai guide" in text


@pytest.mark.unit
def test_merge_sparse_vectors_sums_shared_indices():
    left = SparseVector(indices=[1, 2], values=[0.5, 0.3])
    right = SparseVector(indices=[2, 3], values=[0.2, 0.7])
    merged = merge_sparse_vectors([left, right])
    assert merged.indices == [1, 2, 3]
    assert merged.values == [0.5, 0.5, 0.7]


@pytest.mark.unit
def test_embed_sparse_query_merges_variant_embeddings():
    class FakeEmbedding:
        def __init__(self, indices: list[int], values: list[float]) -> None:
            self.indices = indices
            self.values = values

    class FakeSparseModel:
        def embed(self, texts: list[str]):
            mapping = {
                "open ai": FakeEmbedding([10], [1.0]),
                "openai": FakeEmbedding([20], [0.8]),
            }
            return [mapping[text] for text in texts]

    vector = embed_sparse_query(FakeSparseModel(), "open ai")
    assert vector.indices == [10, 20]
    assert vector.values == [1.0, 0.8]
