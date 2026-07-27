import logging
from langsmith import traceable
from pydantic_ai import Agent

from app.core.config import Settings
from app.schemas.search import SearchSource
from app.schemas.v4.rag import EvidenceAssessmentResult
from app.services.v2.prompts import load_prompt
from app.services.v4.llm import get_pydantic_ai_model

logger = logging.getLogger(__name__)


class InsufficientEvidenceError(Exception):
    """Exception raised when retrieved evidence is insufficient to answer the query."""

    def __init__(self, message: str):
        super().__init__(message)


class EvidenceAssessor:
    """Assess whether retrieved sources contain sufficient information to answer the user query."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("evidence_assessor_system.txt")

    @traceable(name="EvidenceAssessor.evaluate", run_type="chain")
    def evaluate(
        self,
        query: str,
        sources: list[SearchSource],
        *,
        use_cloud_llm: bool = False,
        model: str | None = None,
        system_override: str | None = None,
    ) -> EvidenceAssessmentResult:
        effective_model = model or self._model
        effective_system = system_override or self._system

        if not sources:
            return EvidenceAssessmentResult(
                is_sufficient=False,
                reasoning="No retrieved sources available to assess.",
                missing_information="All information is missing as no sources were retrieved.",
            )

        source_lines = []
        for index, source in enumerate(sources, start=1):
            source_lines.append(
                f"Source {index} - [{source.modality}] Title: {source.title}\n"
                f"Content: {source.content}"
            )
        
        user_prompt = (
            f"User Query: {query.strip()}\n\n"
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
                output_type=EvidenceAssessmentResult,
                system_prompt=effective_system,
            )

            logger.info(
                "Running evidence sufficiency assessment with model=%s, use_cloud_llm=%s",
                effective_model,
                use_cloud_llm,
            )
            result = agent.run_sync(user_prompt)
            return result.data

        except Exception as exc:
            logger.warning(
                "PydanticAI evidence assessment failed; defaulting to sufficient: %s", exc
            )
            return EvidenceAssessmentResult(
                is_sufficient=True,
                reasoning=f"Assessment failed with exception: {exc}. Defaulted to True to avoid block.",
                missing_information=None,
            )
