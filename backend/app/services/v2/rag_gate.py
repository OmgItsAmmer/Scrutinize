import logging
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.services.v2.json_utils import parse_json_object
from app.services.v2.llm_clients import BaseLlmClient, LlmResponse
from app.services.v2.prompts import load_prompt
from app.services.v2.conversation_format import append_conversation_context

logger = logging.getLogger(__name__)

Route = Literal["rag", "generic"]


@dataclass(frozen=True)
class GateResult:
    route: Route
    reason: str
    reply: str | None = None
    llm_call: LlmResponse | None = None


class RagGate:
    """Route generic vs RAG using the current query and full conversation snapshot."""

    def __init__(self, client: BaseLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("rag_gate_system.txt")

    def classify(
        self,
        original: str,
        *,
        conversation_context: str = "",
    ) -> GateResult:
        user_lines = [f"Current user query: {original.strip()}"]
        append_conversation_context(user_lines, conversation_context)

        llm_response = None
        try:
            llm_response = self._client.generate(
                self._model,
                self._system,
                "\n".join(user_lines),
            )
            raw = llm_response.content
            data = parse_json_object(raw)
            route_raw = str(data.get("route", "generic")).strip().lower()
            route: Route = "rag" if route_raw == "rag" else "generic"
            reason = str(data.get("reason", "")).strip() or "No reason provided"
            reply_raw = data.get("reply")
            reply = str(reply_raw).strip() if reply_raw not in (None, "", "null") else None
            if route == "generic" and not reply:
                reply = None
            return GateResult(route=route, reason=reason, reply=reply, llm_call=llm_response)
        except Exception as exc:
            logger.warning("RAG gate generation/parse failed; defaulting to generic: %s", exc)
            return GateResult(
                route="generic",
                reason=f"Gate failed; defaulting to generic: {exc}",
                llm_call=llm_response,
            )
