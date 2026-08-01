"""Cross-encoder reranking of RRF-fused candidates (V5 M2).

Reranking is a post-fusion refinement, never a new failure mode: if the model
fails to load or exceeds the timeout budget, callers fall back to RRF order.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace

from app.core.config import Settings
from app.schemas.search import SearchSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankedSource:
    source: SearchSource
    rrf_rank: int  # 1-indexed position before reranking
    rerank_score: float | None  # None if reranking was skipped/failed for this batch


@dataclass(frozen=True)
class RerankResult:
    sources: list[RerankedSource]
    applied: bool  # False if reranking failed/timed out and RRF order was kept
    latency_ms: int
    error: str | None = None


class Reranker:
    """Lazily-loaded cross-encoder reranker, mirroring VectorStore.sparse_model's lazy pattern."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker")

    @property
    def model(self) -> object:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(model_name=self._settings.rerank_model)
        return self._model

    def rerank(
        self,
        query: str,
        sources: list[SearchSource],
        *,
        top_k: int,
    ) -> RerankResult:
        started = time.monotonic()
        ranked = [
            RerankedSource(source=source, rrf_rank=rank, rerank_score=None)
            for rank, source in enumerate(sources, start=1)
        ]

        if not self._settings.rerank_enabled or not sources:
            return RerankResult(sources=ranked[:top_k], applied=False, latency_ms=0)

        try:
            future = self._executor.submit(self._score, query, sources)
            scores = future.result(timeout=self._settings.rerank_timeout_s)
        except FutureTimeoutError:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.warning(
                "Reranker timed out after %.1fs; falling back to RRF order.",
                self._settings.rerank_timeout_s,
            )
            return RerankResult(
                sources=ranked[:top_k],
                applied=False,
                latency_ms=latency_ms,
                error="timeout",
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.warning("Reranker failed (%s); falling back to RRF order.", exc)
            return RerankResult(
                sources=ranked[:top_k],
                applied=False,
                latency_ms=latency_ms,
                error=str(exc),
            )

        scored = [
            replace(item, rerank_score=float(score))
            for item, score in zip(ranked, scores, strict=True)
        ]
        scored.sort(key=lambda item: item.rerank_score, reverse=True)
        latency_ms = int((time.monotonic() - started) * 1000)
        return RerankResult(sources=scored[:top_k], applied=True, latency_ms=latency_ms)

    def _score(self, query: str, sources: list[SearchSource]) -> list[float]:
        documents = [source.content for source in sources]
        return list(self.model.rerank(query, documents))
