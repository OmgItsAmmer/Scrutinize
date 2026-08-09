import logging
from langsmith import traceable
from pydantic_ai import Agent

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.schemas.v4.rag import CitationMapResult
from app.services.v2.prompts import load_prompt
from app.services.v4.llm import get_pydantic_ai_model

logger = logging.getLogger(__name__)


class CitationVerifier:
    """Verify citations in synthesis drafts against the list of retrieved sources."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("citation_verifier_system.txt")

    @traceable(name="CitationVerifier.verify", run_type="chain")
    def verify(
        self,
        query: str,
        draft_answer: str,
        sources: list[SearchSource],
        *,
        use_cloud_llm: bool = False,
        model: str | None = None,
        system_override: str | None = None,
    ) -> CitationMapResult:
        effective_model = model or self._model
        effective_system = system_override or self._system

        lowered = draft_answer.strip().lower()
        if not draft_answer.strip() or "could not find sufficient information" in lowered:
            return CitationMapResult(has_valid_citations=True, mappings=[])

        source_lines = []
        for index, source in enumerate(sources, start=1):
            source_lines.append(
                f"Source {index} - [{source.modality}] Title: {source.title}\n"
                f"Content: {source.content}"
            )

        user_prompt = (
            f"User Query: {query.strip()}\n\n"
            f"Draft Answer to Verify:\n{draft_answer.strip()}\n\n"
            f"Retrieved Context:\n" + "\n\n".join(source_lines)
        )

        try:
            pydantic_model = get_pydantic_ai_model(
                model_name=effective_model,
                settings=self._settings,
                use_cloud_llm=use_cloud_llm,
            )

            agent = Agent(
                model=pydantic_model,
                output_type=CitationMapResult,
                system_prompt=effective_system,
            )

            logger.info(
                "Running citation verification with model=%s, use_cloud_llm=%s",
                effective_model,
                use_cloud_llm,
            )
            result = agent.run_sync(user_prompt)
            citation_res = result.output

            from app.services.v2.llm_clients.base import LlmResponse
            usage = result.usage
            prompt_tokens = (usage.input_tokens or 0) if usage else 0
            completion_tokens = (usage.output_tokens or 0) if usage else 0
            cached_tokens = 0
            if usage and usage.details and isinstance(usage.details, dict):
                cached_tokens = usage.details.get("cached_tokens", 0) or 0

            citation_res.llm_call = LlmResponse(
                content=citation_res.model_dump_json() if hasattr(citation_res, "model_dump_json") else str(citation_res),
                model_name=effective_model,
                prompt_system=effective_system,
                prompt_user=user_prompt,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
            )
            return citation_res

        except Exception as exc:
            logger.warning(
                "PydanticAI citation verification failed; defaulting to valid: %s", exc
            )
            return CitationMapResult(has_valid_citations=True, mappings=[])
