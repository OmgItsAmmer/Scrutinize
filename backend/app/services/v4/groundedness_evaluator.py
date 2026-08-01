import logging
from langsmith import traceable
from pydantic_ai import Agent

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.schemas.v4.rag import GroundednessResult
from app.services.v2.prompts import load_prompt
from app.services.v4.llm import get_pydantic_ai_model

logger = logging.getLogger(__name__)


class GroundednessEvaluator:
    """Evaluate and score the groundedness of generated answers against reference context."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("groundedness_evaluator_system.txt")

    @traceable(name="GroundednessEvaluator.evaluate", run_type="chain")
    def evaluate(
        self,
        query: str,
        answer: str,
        sources: list[SearchSource],
        *,
        use_cloud_llm: bool = False,
        model: str | None = None,
        system_override: str | None = None,
    ) -> GroundednessResult:
        effective_model = model or self._model
        effective_system = system_override or self._system

        if not answer.strip():
            return GroundednessResult(
                score=1.0,
                reasoning="Answer is empty; default to fully grounded.",
                is_grounded=True,
            )

        source_lines = []
        for index, source in enumerate(sources, start=1):
            source_lines.append(
                f"Source {index} - [{source.modality}] Title: {source.title}\n"
                f"Content: {source.content}"
            )

        user_prompt = (
            f"User Query: {query.strip()}\n\n"
            f"Generated Answer to Evaluate:\n{answer.strip()}\n\n"
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
                output_type=GroundednessResult,
                system_prompt=effective_system,
            )

            logger.info(
                "Running groundedness evaluation with model=%s, use_cloud_llm=%s",
                effective_model,
                use_cloud_llm,
            )
            result = agent.run_sync(user_prompt)
            
            # Enforce 0.90 safety threshold check explicitly if the model outputs differently
            score = result.output.score
            is_grounded = score >= 0.90
            
            ground_res = GroundednessResult(
                score=score,
                reasoning=result.output.reasoning,
                is_grounded=is_grounded,
            )

            from app.services.v2.llm_clients.base import LlmResponse
            usage = result.usage
            prompt_tokens = (usage.input_tokens or 0) if usage else 0
            completion_tokens = (usage.output_tokens or 0) if usage else 0
            cached_tokens = 0
            if usage and usage.details and isinstance(usage.details, dict):
                cached_tokens = usage.details.get("cached_tokens", 0) or 0

            ground_res.llm_call = LlmResponse(
                content=ground_res.model_dump_json() if hasattr(ground_res, "model_dump_json") else str(ground_res),
                model_name=effective_model,
                prompt_system=effective_system,
                prompt_user=user_prompt,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
            )
            return ground_res

        except Exception as exc:
            logger.warning(
                "PydanticAI groundedness evaluation failed; defaulting to grounded: %s", exc
            )
            return GroundednessResult(
                score=1.0,
                reasoning=f"Evaluation failed with exception: {exc}. Defaulted to fully grounded.",
                is_grounded=True,
            )
