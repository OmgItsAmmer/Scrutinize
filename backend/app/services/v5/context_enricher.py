"""Contextual retrieval: generate a short situating header per chunk (V5 Phase 3 M6).

A chunk stripped of its document context embeds poorly. Prepending a
generated header before embedding is the "contextual retrieval" technique —
cheap because the document prefix is identical across every chunk in a file,
so it hits the LLM provider's automatic prompt-prefix cache instead of being
priced (and latency-charged) as fresh input on every call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import tiktoken

from app.core.config import Settings
from app.services.v2.llm_clients.base import BaseLlmClient
from app.services.v2.prompts import load_prompt

logger = logging.getLogger(__name__)

_ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class EnrichedChunk:
    context_header: str
    used_llm: bool  # False when the document exceeded contextual_max_doc_tokens
    prompt_tokens: int = 0
    cached_tokens: int = 0


def _count_tokens(text: str) -> int:
    encoding = tiktoken.get_encoding(_ENCODING_NAME)
    return len(encoding.encode(text))


def _fallback_header(title: str, section_path: str | None) -> str:
    """No-LLM header for oversized documents: title + section_path only."""
    if section_path:
        return f"From {title}, section: {section_path}."
    return f"From {title}."


class ContextEnricher:
    """Generates a 1-2 sentence header situating a chunk within its document."""

    def __init__(self, client: BaseLlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._system = load_prompt("context_enricher_system.txt")

    def enrich(
        self,
        *,
        document_text: str,
        chunk_text: str,
        title: str,
        section_path: str | None = None,
    ) -> EnrichedChunk:
        if not self._settings.contextual_retrieval_enabled:
            return EnrichedChunk(context_header="", used_llm=False)

        doc_tokens = _count_tokens(document_text)
        if doc_tokens > self._settings.contextual_max_doc_tokens:
            return EnrichedChunk(
                context_header=_fallback_header(title, section_path),
                used_llm=False,
            )

        # Document content first (identical prefix across every chunk in this
        # file) so the provider's automatic prefix cache actually applies —
        # only the trailing chunk-specific text varies between calls.
        user_prompt = (
            f"Document:\n{document_text}\n\n"
            f"---\n\nChunk to describe:\n{chunk_text}"
        )

        try:
            response = self._client.generate(
                self._settings.contextual_context_model,
                self._system,
                user_prompt,
            )
        except Exception:
            logger.exception("Context enrichment LLM call failed; falling back to title/section header.")
            return EnrichedChunk(
                context_header=_fallback_header(title, section_path),
                used_llm=False,
            )

        header = response.content.strip()
        if not header:
            return EnrichedChunk(
                context_header=_fallback_header(title, section_path),
                used_llm=False,
            )

        return EnrichedChunk(context_header=header, used_llm=True)
