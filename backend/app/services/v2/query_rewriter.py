from dataclasses import dataclass

from app.core.config import Settings
from app.services.v2.conversation_format import (
    append_conversation_context,
    is_contextual_follow_up,
    is_standalone_message,
)
from app.services.v2.local_llm_client import LocalLlmClient
from app.services.v2.prompts import load_prompt


@dataclass(frozen=True)
class RewrittenQuery:
    text: str


class QueryRewriter:
    """qwen3.5:2b — rewrite user queries for better retrieval keywords."""

    def __init__(self, client: LocalLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_rewriter_model
        self._system = load_prompt("query_rewriter_system.txt")

    def rewrite(
        self,
        query: str,
        feedback: str | None = None,
        *,
        conversation_context: str = "",
    ) -> RewrittenQuery:
        stripped = query.strip()
        if is_standalone_message(stripped):
            return RewrittenQuery(text=stripped)

        user_lines = [f"User query: {stripped}"]
        if feedback and feedback.strip():
            user_lines.append(f"Revision feedback: {feedback.strip()}")

        use_context = bool(feedback and feedback.strip()) or is_contextual_follow_up(stripped)
        if use_context:
            append_conversation_context(user_lines, conversation_context)

        raw = self._client.generate(
            self._model,
            self._system,
            "\n".join(user_lines),
        )
        rewritten = raw.strip() or stripped
        return RewrittenQuery(text=rewritten)
