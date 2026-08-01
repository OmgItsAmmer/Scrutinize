from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services.v2.llm_clients.base import LlmResponse
from app.services.v5.context_enricher import ContextEnricher


def _settings(**overrides) -> Settings:
    return Settings(local_llm_base_url="http://llm.test", **overrides)


@pytest.mark.unit
def test_enrich_disabled_returns_empty_header():
    client = MagicMock()
    enricher = ContextEnricher(client, _settings(contextual_retrieval_enabled=False))

    result = enricher.enrich(document_text="doc", chunk_text="chunk", title="a.pdf")

    assert result.context_header == ""
    assert result.used_llm is False
    client.generate.assert_not_called()


@pytest.mark.unit
def test_enrich_calls_llm_with_document_as_prefix():
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="This chunk covers payment terms in the vendor contract.",
        model_name="gpt-4o-mini",
        prompt_system="sys",
        prompt_user="user",
    )
    enricher = ContextEnricher(client, _settings())

    result = enricher.enrich(
        document_text="Full vendor contract text here.",
        chunk_text="Invoices are due within 30 days.",
        title="vendor_contract.pdf",
        section_path="Payment Terms",
    )

    assert result.used_llm is True
    assert "payment terms" in result.context_header.lower()
    args, kwargs = client.generate.call_args
    user_prompt = args[2]
    # Document text must come first (fixed prefix) so provider prompt caching applies;
    # the chunk-specific text is appended after it.
    assert user_prompt.index("Full vendor contract text here.") < user_prompt.index(
        "Invoices are due within 30 days."
    )


@pytest.mark.unit
def test_enrich_falls_back_to_title_section_header_for_oversized_documents():
    client = MagicMock()
    enricher = ContextEnricher(client, _settings(contextual_max_doc_tokens=5))

    result = enricher.enrich(
        document_text="word " * 1000,
        chunk_text="chunk",
        title="big_doc.pdf",
        section_path="Intro",
    )

    assert result.used_llm is False
    assert "big_doc.pdf" in result.context_header
    assert "Intro" in result.context_header
    client.generate.assert_not_called()


@pytest.mark.unit
def test_enrich_fails_open_on_llm_error():
    client = MagicMock()
    client.generate.side_effect = RuntimeError("LLM unavailable")
    enricher = ContextEnricher(client, _settings())

    result = enricher.enrich(document_text="doc", chunk_text="chunk", title="a.pdf")

    assert result.used_llm is False
    assert "a.pdf" in result.context_header


@pytest.mark.unit
def test_enrich_falls_back_when_llm_returns_empty_content():
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="   ",
        model_name="gpt-4o-mini",
        prompt_system="sys",
        prompt_user="user",
    )
    enricher = ContextEnricher(client, _settings())

    result = enricher.enrich(document_text="doc", chunk_text="chunk", title="a.pdf")

    assert result.used_llm is False
    assert "a.pdf" in result.context_header
