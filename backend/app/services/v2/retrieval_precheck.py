"""Cheap retrieval pre-check to skip gate LLM when routing is clear."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from langsmith import traceable

from app.core.config import Settings
from app.models.file import FileModality
from app.services.v2.retrieval_utils import RetrieveResult
from app.services.v2.rrf_retriever import RrfRetriever

logger = logging.getLogger(__name__)

PrecheckAction = Literal["call_gate", "route_rag", "route_web", "route_generic"]
_NULL_PROJECT_ID = UUID(int=0)


@dataclass(frozen=True)
class RetrievalPrecheckResult:
    action: PrecheckAction
    reason: str
    top_score: float | None
    retrieval: RetrieveResult | None = None


class RetrievalPrecheck:
    """Embed + retrieve top-k once; gate LLM only when scores are ambiguous."""

    def __init__(self, retriever: RrfRetriever, settings: Settings) -> None:
        self._retriever = retriever
        self._settings = settings

    @traceable(name="RetrievalPrecheck.evaluate", run_type="chain")
    def evaluate(
        self,
        query: str,
        *,
        project_id: UUID | None,
        conversation_id: UUID | None,
        has_corpus: bool,
        modality_filter: FileModality | None = None,
        client_requested_tool: str | None = None,
        enable_web_search: bool = True,
    ) -> RetrievalPrecheckResult:
        if client_requested_tool in ("generate_pdf", "generate_flowchart") and has_corpus:
            return RetrievalPrecheckResult(
                action="route_rag",
                reason=f"Tool {client_requested_tool} selected; retrieval required before export/rendering.",
                top_score=None,
            )

        if client_requested_tool:
            return RetrievalPrecheckResult(
                action="call_gate",
                reason=f"Tool selected ({client_requested_tool}); gate decides routing.",
                top_score=None,
            )

        if not has_corpus:
            if enable_web_search:
                return RetrievalPrecheckResult(
                    action="route_web",
                    reason="No indexed sources available; using web search.",
                    top_score=None,
                )
            return RetrievalPrecheckResult(
                action="route_generic",
                reason="No indexed sources available.",
                top_score=None,
            )

        effective_project_id = project_id or _NULL_PROJECT_ID
        include_project_wide = project_id is not None
        # Skip reranking here: this call only needs an approximate top score to
        # compare against the high/low thresholds below, not a precisely ordered
        # top-3. The final RrfRetriever.retrieve() call after rewrite still
        # reranks properly — doubling that (expensive, single-worker) cost here
        # for a value that gets thrown away is pure added latency.
        retrieval = self._retriever.retrieve(
            query,
            project_id=effective_project_id,
            modality_filter=modality_filter,
            top_k=3,
            conversation_id=conversation_id,
            include_project_wide=include_project_wide,
            apply_rerank=False,
        )
        top_score = retrieval.sources[0].score if retrieval.sources else 0.0
        high = self._settings.v2_retrieval_precheck_high_score
        low = self._settings.v2_retrieval_precheck_low_score

        if top_score >= high:
            return RetrievalPrecheckResult(
                action="route_rag",
                reason=f"Retrieval pre-check score {top_score:.4f} >= {high:.4f}.",
                top_score=top_score,
                retrieval=retrieval,
            )

        if top_score <= low:
            if enable_web_search:
                return RetrievalPrecheckResult(
                    action="route_web",
                    reason=f"Retrieval pre-check score {top_score:.4f} <= {low:.4f}; web preferred.",
                    top_score=top_score,
                    retrieval=retrieval,
                )
            return RetrievalPrecheckResult(
                action="route_generic",
                reason=f"Retrieval pre-check score {top_score:.4f} <= {low:.4f}.",
                top_score=top_score,
                retrieval=retrieval,
            )

        return RetrievalPrecheckResult(
            action="call_gate",
            reason=f"Retrieval score {top_score:.4f} ambiguous ({low:.4f}–{high:.4f}); calling gate.",
            top_score=top_score,
            retrieval=retrieval,
        )
