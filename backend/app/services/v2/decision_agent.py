import logging
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.services.v2.conversation_format import append_conversation_context
from app.services.v2.json_utils import parse_json_object
from app.services.v2.local_llm_client import LocalLlmClient
from app.services.v2.prompts import load_prompt
from app.services.v2.rag_gate import Route

logger = logging.getLogger(__name__)

Verdict = Literal["good", "retry"]


@dataclass(frozen=True)
class DecisionContext:
    original_query: str
    rewritten_query: str
    route: Route
    draft_answer: str
    sources: list[SearchSource]
    attempt: int
    conversation_context: str = ""


@dataclass(frozen=True)
class DecisionResult:
    verdict: Verdict
    confidence: float
    feedback: str
    correct_route: Route | None = None


class DecisionAgent:
    """qwen3.5:4b — score draft answer quality and suggest retries."""

    def __init__(self, client: LocalLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_decision_model
        self._system = load_prompt("decision_agent_system.txt")

    def evaluate(self, context: DecisionContext) -> DecisionResult:
        chunk_lines = _format_chunk_summaries(context.sources)
        user_lines = [
            f"Attempt: {context.attempt}",
            f"Route: {context.route}",
            f"Original query: {context.original_query.strip()}",
            f"Rewritten query: {context.rewritten_query.strip()}",
            f"Draft answer: {context.draft_answer.strip()}",
            f"Retrieved chunks:\n{chunk_lines or '(none)'}",
        ]
        append_conversation_context(user_lines, context.conversation_context)

        raw = self._client.generate(self._model, self._system, "\n".join(user_lines))

        try:
            data = parse_json_object(raw)
            verdict_raw = str(data.get("verdict", "retry")).strip().lower()
            verdict: Verdict = "good" if verdict_raw == "good" else "retry"
            confidence = _clamp_confidence(data.get("confidence", 0.0))
            feedback = str(data.get("feedback", "")).strip()
            route_raw = str(data.get("correct_route", "")).strip().lower()
            correct_route: Route | None = None
            if route_raw in ("rag", "generic"):
                correct_route = route_raw  # type: ignore[assignment]
            return DecisionResult(
                verdict=verdict,
                confidence=confidence,
                feedback=feedback,
                correct_route=correct_route,
            )
        except (ValueError, TypeError) as exc:
            logger.warning("Decision agent JSON parse failed; defaulting to retry: %s", exc)
            return DecisionResult(
                verdict="retry",
                confidence=0.0,
                feedback="Decision JSON parse failed; broaden query keywords.",
            )


def _format_chunk_summaries(sources: list[SearchSource]) -> str:
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        content = source.content.strip()
        if len(content) > 240:
            content = f"{content[:237]}..."
        lines.append(f"{index}. [{source.modality}] {source.title}: {content}")
    return "\n".join(lines)


def _clamp_confidence(value: object) -> float:
    try:
        confidence = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
