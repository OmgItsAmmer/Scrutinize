import logging
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.services.v2.json_utils import parse_json_object
from app.services.v2.local_llm_client import LocalLlmClient
from app.services.v2.prompts import load_prompt
from app.services.v2.conversation_format import append_conversation_context

logger = logging.getLogger(__name__)

Route = Literal["rag", "generic"]


@dataclass(frozen=True)
class GateResult:
    route: Route
    reason: str
    reply: str | None = None


class RagGate:
    """qwen3.5:0.8b — route generic vs RAG; includes direct reply for generic."""

    def __init__(self, client: LocalLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("rag_gate_system.txt")

    def classify(
        self,
        original: str,
        *,
        rewritten: str = "",
        conversation_context: str = "",
    ) -> GateResult:
        user_lines = [f"Original query: {original.strip()}"]
        if rewritten.strip():
            user_lines.append(f"Rewritten query: {rewritten.strip()}")
        append_conversation_context(user_lines, conversation_context)

        raw = self._client.generate(
            self._model,
            self._system,
            "\n".join(user_lines),
        )

        try:
            data = parse_json_object(raw)
            route_raw = str(data.get("route", "rag")).strip().lower()
            route: Route = "rag" if route_raw == "rag" else "generic"
            reason = str(data.get("reason", "")).strip() or "No reason provided"
            reply_raw = data.get("reply")
            reply = str(reply_raw).strip() if reply_raw not in (None, "", "null") else None
            if route == "generic" and not reply:
                reply = None
            return GateResult(route=route, reason=reason, reply=reply)
        except (ValueError, TypeError) as exc:
            logger.warning("RAG gate JSON parse failed; defaulting to rag: %s", exc)
            return GateResult(
                route="rag",
                reason="Gate JSON parse failed; defaulting to RAG",
            )
