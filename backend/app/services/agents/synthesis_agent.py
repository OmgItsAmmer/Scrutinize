from openai import OpenAI

from app.core.config import Settings
from app.schemas.search import SearchSource


class SynthesisAgent:
    """GPT-4o-mini answer synthesis over retrieved segments."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for answer synthesis.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.synthesis_model

    def synthesize(self, query: str, sources: list[SearchSource]) -> str:
        if not sources:
            return "No matching indexed content was found for your question."

        lines: list[str] = []
        for index, source in enumerate(sources, start=1):
            time_label = _format_time_range(source.start_time, source.end_time)
            lines.append(
                f"{index}. [{source.modality}] {source.title} {time_label} "
                f"(score={source.score:.3f}): {source.content}"
            )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You answer questions using only the provided source segments. "
                        "Give a concise natural-language answer and cite file names with "
                        "timestamps when available. If nothing matches, say so clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n\nSources:\n" + "\n".join(lines)
                    ),
                },
            ],
            max_tokens=500,
        )
        content = response.choices[0].message.content
        if not content:
            return "Unable to synthesize an answer from the retrieved segments."
        return content.strip()


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
