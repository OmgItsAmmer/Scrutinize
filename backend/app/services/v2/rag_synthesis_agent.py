from dataclasses import dataclass
from typing import Iterator
from langsmith import traceable

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.services.v2.conversation_format import append_conversation_context
from app.services.v2.llm_clients import BaseLlmClient, LlmResponse
from app.services.v2.prompts import load_prompt


@dataclass(frozen=True)
class SynthesisResult:
    answer: str
    llm_call: LlmResponse | None = None


class RagSynthesisAgent:
    """Local LLM answer synthesis over retrieved segments."""

    def __init__(self, client: BaseLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_rewriter_model
        self._system = load_prompt("rag_synthesis_system.txt")

    @traceable(name="RagSynthesisAgent.synthesize", run_type="chain")
    def synthesize(
        self,
        query: str,
        sources: list[SearchSource],
        *,
        model: str | None = None,
        system_override: str | None = None,
        conversation_context: str = "",
        tools: list[dict] | None = None,
    ) -> SynthesisResult:
        effective_model = model or self._model
        effective_system = system_override or self._system
        if tools:
            effective_system += "\n\n### PDF GENERATION TOOL RULE:\nIf the user explicitly asks to generate a PDF or compile a document, you MUST invoke the 'generate_pdf' tool."
        
        from app.services.v5.untrusted import wrap_untrusted
        user_lines = [
            f"Question: {query.strip()}",
            "",
            "Sources:",
            wrap_untrusted(sources),
        ]
        append_conversation_context(user_lines, conversation_context)

        llm_response = self._client.generate(
            effective_model,
            effective_system,
            "\n".join(user_lines),
            tools=tools
        )
        return SynthesisResult(
            answer=llm_response.content,
            llm_call=llm_response,
        )

    def synthesize_stream(
        self,
        query: str,
        sources: list[SearchSource],
        *,
        model: str | None = None,
        system_override: str | None = None,
        conversation_context: str = "",
    ) -> Iterator[str]:
        effective_model = model or self._model
        effective_system = system_override or self._system
        from app.services.v5.untrusted import wrap_untrusted
        user_lines = [
            f"Question: {query.strip()}",
            "",
            "Sources:",
            wrap_untrusted(sources),
        ]
        append_conversation_context(user_lines, conversation_context)

        return self._client.generate_stream(
            effective_model,
            effective_system,
            "\n".join(user_lines),
        )




def _seconds_to_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_time_range(start_time: float | None, end_time: float | None) -> str:
    if start_time is None and end_time is None:
        return ""
    if start_time is not None and end_time is not None:
        return f"[{_seconds_to_timestamp(start_time)}–{_seconds_to_timestamp(end_time)}]"
    if start_time is not None:
        return f"[{_seconds_to_timestamp(start_time)}]"
    return f"[–{_seconds_to_timestamp(end_time)}]" if end_time is not None else ""


def _format_position_label(page_number: int | None, section_path: str | None) -> str:
    """" p. 7 — §2.1 Payment Terms" style suffix; empty when no position metadata exists."""
    parts: list[str] = []
    if page_number is not None:
        parts.append(f"p. {page_number}")
    if section_path:
        parts.append(f"§{section_path}")
    if not parts:
        return ""
    return " (" + " — ".join(parts) + ")"
