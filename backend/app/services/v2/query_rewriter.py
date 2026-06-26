from dataclasses import dataclass

from app.core.config import Settings
from app.services.v2.conversation_format import (
    append_conversation_context,
    is_standalone_message,
)
from app.services.v2.llm_clients import BaseLlmClient, LlmResponse
from app.services.v2.prompts import load_prompt


@dataclass(frozen=True)
class RewrittenQuery:
    text: str
    llm_call: LlmResponse | None = None


class QueryRewriter:
    """Rewrite user queries for better retrieval keywords (RAG path only)."""

    def __init__(self, client: BaseLlmClient, settings: Settings) -> None:
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
            return RewrittenQuery(text=stripped, llm_call=None)

        user_lines = [f"User query: {stripped}"]
        if feedback and feedback.strip():
            user_lines.append(f"Revision feedback: {feedback.strip()}")
        append_conversation_context(user_lines, conversation_context)

        llm_response = self._client.generate(
            self._model,
            self._system,
            "\n".join(user_lines),
        )
        rewritten = llm_response.content.strip() or stripped
        return RewrittenQuery(text=rewritten, llm_call=llm_response)
