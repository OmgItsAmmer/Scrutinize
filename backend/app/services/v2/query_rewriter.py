import re
from dataclasses import dataclass
from langsmith import traceable

from app.core.config import Settings
from app.services.v2.conversation_format import (
    append_conversation_context,
    is_standalone_message,
)
from app.services.v2.llm_clients import BaseLlmClient, LlmResponse
from app.services.v2.prompts import load_prompt

# Some project-specific rewriter prompts (auto-generated per project, see
# prompt_generator.py) omit the "output only the query" constraint that the
# default prompt enforces. Models then prepend labels like "Optimized search
# query:" or wrap the result in quotes, which pollutes the embedding/keyword
# vectors built from this text. Strip that defensively regardless of prompt
# quality, since it is cheap and this text feeds retrieval directly.
_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:optimized|rewritten|revised|final|search)\s+(?:search\s+)?quer(?:y|ies)\s*:\s*",
    re.IGNORECASE,
)
_WRAPPING_QUOTES = ('"', "'", "“”", "‘’")


def _sanitize_rewrite(text: str) -> str:
    cleaned = _LABEL_PREFIX_RE.sub("", text).strip()
    for quotes in _WRAPPING_QUOTES:
        open_q, close_q = quotes[0], quotes[-1]
        if len(cleaned) >= 2 and cleaned[0] == open_q and cleaned[-1] == close_q:
            cleaned = cleaned[1:-1].strip()
            break
    return cleaned


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

    @traceable(name="QueryRewriter.rewrite", run_type="chain")
    def rewrite(
        self,
        query: str,
        feedback: str | None = None,
        *,
        model: str | None = None,
        system_override: str | None = None,
        conversation_context: str = "",
    ) -> RewrittenQuery:
        stripped = query.strip()
        if is_standalone_message(stripped):
            return RewrittenQuery(text=stripped, llm_call=None)

        effective_model = model or self._model
        effective_system = system_override or self._system
        
        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        day_of_week = now.strftime("%A")
        effective_system = f"Current Date: {date_str} ({day_of_week})\n\n{effective_system}"

        user_lines = [f"User query: {stripped}"]
        if feedback and feedback.strip():
            user_lines.append(f"Revision feedback: {feedback.strip()}")
        append_conversation_context(user_lines, conversation_context)

        llm_response = self._client.generate(
            effective_model,
            effective_system,
            "\n".join(user_lines),
        )
        rewritten = _sanitize_rewrite(llm_response.content) or stripped
        return RewrittenQuery(text=rewritten, llm_call=llm_response)


