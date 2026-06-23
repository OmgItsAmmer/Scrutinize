from app.core.config import Settings
from app.schemas.search import SearchSource
from app.services.v2.conversation_format import append_conversation_context
from app.services.v2.local_llm_client import LocalLlmClient
from app.services.v2.prompts import load_prompt


class RagSynthesisAgent:
    """Local LLM answer synthesis over retrieved segments."""

    def __init__(self, client: LocalLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_rewriter_model
        self._system = load_prompt("rag_synthesis_system.txt")

    def synthesize(
        self,
        query: str,
        sources: list[SearchSource],
        *,
        conversation_context: str = "",
    ) -> str:
        lines: list[str] = []
        for index, source in enumerate(sources, start=1):
            time_label = _format_time_range(source.start_time, source.end_time)
            lines.append(
                f"{index}. [{source.modality}] {source.title} {time_label} "
                f"(score={source.score:.3f}): {source.content}"
            )

        user_lines = [f"Question: {query.strip()}", "", "Sources:", *lines]
        append_conversation_context(user_lines, conversation_context)
        return self._client.generate(self._model, self._system, "\n".join(user_lines))


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
