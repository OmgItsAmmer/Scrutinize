import json
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import Settings
from app.models.file import FileModality

ROUTE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "route_search_query",
        "description": (
            "Rewrite a natural-language question for semantic vector search and "
            "optionally restrict results to text, audio, or video when the user "
            "clearly targets one modality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": (
                        "Rewritten query optimized for embedding similarity search."
                    ),
                },
                "modality_filter": {
                    "type": "string",
                    "enum": ["text", "audio", "video"],
                    "description": (
                        "Set only when the user explicitly asks for a text document, "
                        "song/audio clip, or video."
                    ),
                },
            },
            "required": ["search_query"],
        },
    },
}


@dataclass(frozen=True)
class RouterResult:
    search_query: str
    modality_filter: FileModality | None = None


class RouterAgent:
    """GPT-4o-mini router: modality filter + rewritten search query."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for query routing.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.router_model

    def route(self, query: str) -> RouterResult:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You route multimodal search queries. Call route_search_query with "
                        "a concise search_query suitable for embedding search. Set "
                        "modality_filter only when the user clearly wants text, audio, or video."
                    ),
                },
                {"role": "user", "content": query},
            ],
            tools=[ROUTE_SEARCH_TOOL],
            tool_choice={"type": "function", "function": {"name": "route_search_query"}},
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return RouterResult(search_query=query.strip())

        arguments = json.loads(tool_calls[0].function.arguments)
        search_query = str(arguments.get("search_query", query)).strip() or query.strip()
        modality_raw = arguments.get("modality_filter")
        modality_filter = None
        if modality_raw in {item.value for item in FileModality}:
            modality_filter = FileModality(modality_raw)
        return RouterResult(search_query=search_query, modality_filter=modality_filter)
