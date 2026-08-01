from datetime import UTC, datetime
import logging
from uuid import UUID

from sqlmodel import Session, select

from app.models.file import FileModality
from app.models.pipeline_log import PipelineRun, PipelineStep
from app.schemas.search import SearchSource
from app.services.v2.rag_gate import GateResult
from app.services.v2.query_rewriter import RewrittenQuery
from app.services.v2.generic_agent import GenericReplyResult
from app.services.v2.rag_synthesis_agent import SynthesisResult
from app.services.v2.decision_agent import DecisionResult
from app.services.v2.retrieval_utils import RetrievalStats

logger = logging.getLogger(__name__)


class PipelineLogger:
    """Helper class to log v2 search pipeline execution steps to a relational DB using unified tables."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def start_run(
        self,
        query: str,
        modality_filter: FileModality | None,
        conversation_context: str | None,
        project_id: UUID | None = None,
    ) -> UUID | None:
        if not self._session:
            return None

        try:
            run = PipelineRun(
                original_query=query,
                modality_filter=modality_filter,
                conversation_context=conversation_context,
                start_time=datetime.now(UTC),
                project_id=project_id,
            )
            self._session.add(run)
            self._session.commit()
            self._session.refresh(run)
            return run.id
        except Exception:
            logger.exception("Failed to log search pipeline run start to database.")
            return None

    def log_rewrite(
        self,
        run_id: UUID | None,
        attempt: int,
        rewritten: RewrittenQuery,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = rewritten.llm_call
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None
            
            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="rewrite",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={"rewritten_query": rewritten.text},
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log query rewrite step to database.")

    def log_gate(
        self,
        run_id: UUID | None,
        gate_result: GateResult,
        attempt: int | None = None,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            if attempt is None:
                statement = select(PipelineStep).where(
                    PipelineStep.run_id == run_id,
                    PipelineStep.step_type == "gate",
                )
                existing_gates = self._session.exec(statement).all()
                attempt = len(existing_gates) + 1

            llm = gate_result.llm_call
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="gate",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={
                    "route": gate_result.route,
                    "reason": gate_result.reason,
                    "reply": gate_result.reply,
                },
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log RAG gate step to database.")

    def log_retrieval(
        self,
        run_id: UUID | None,
        attempt: int,
        query: str,
        rewritten_query: str,
        sources: list[SearchSource],
        *,
        retrieval_stats: RetrievalStats | None = None,
        source_rank_fields: list[dict] | None = None,
        latency_ms: int = 0,
        prompt_tokens: int | None = None,
        cost_usd: float | None = None,
        model_name: str | None = None,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            serialized_sources = []
            rank_fields_by_index = source_rank_fields or []
            for rank, source in enumerate(sources, start=1):
                entry = {
                    "segment_id": str(source.segment_id) if source.segment_id else None,
                    "file_id": str(source.file_id) if source.file_id else None,
                    "modality": str(source.modality),
                    "title": source.title,
                    "content": source.content,
                    "source_path": source.source_path,
                    "start_time": source.start_time,
                    "end_time": source.end_time,
                    "score": float(source.score),
                    "rank": rank,
                }
                if rank - 1 < len(rank_fields_by_index):
                    entry.update(rank_fields_by_index[rank - 1])
                serialized_sources.append(entry)

            structured_output: dict = {
                "query": query,
                "rewritten_query": rewritten_query,
            }
            if retrieval_stats is not None:
                structured_output["retrieval"] = retrieval_stats.to_dict()

            step = PipelineStep(
                run_id=run_id,
                step_type="retrieval",
                attempt=attempt,
                model_name=model_name,
                model_input=None,
                raw_thinking=None,
                model_output=None,
                structured_output=structured_output,
                retrieved_sources=serialized_sources,
                latency_ms=latency_ms,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                cached_tokens=0,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log retrieval step and sources to database.")

    def log_synthesis(
        self,
        run_id: UUID | None,
        attempt: int,
        synthesis_result: SynthesisResult | GenericReplyResult,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = synthesis_result.llm_call
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None
            answer = (
                synthesis_result.answer
                if isinstance(synthesis_result, SynthesisResult)
                else synthesis_result.answer
            )

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="synthesis",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={"answer": answer},
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log synthesis step to database.")

    def log_evaluation(
        self,
        run_id: UUID | None,
        attempt: int,
        decision: DecisionResult,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = decision.llm_call
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="evaluation",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={
                    "verdict": decision.verdict,
                    "confidence": decision.confidence,
                    "correct_route": decision.correct_route,
                    "feedback": decision.feedback,
                },
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log evaluation step to database.")

    def log_evidence_assessment(
        self,
        run_id: UUID | None,
        attempt: int,
        assessment: object,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = getattr(assessment, "llm_call", None)
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="assess_evidence",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={
                    "is_sufficient": getattr(assessment, "is_sufficient", None),
                    "reasoning": getattr(assessment, "reasoning", None),
                    "missing_information": getattr(assessment, "missing_information", None),
                },
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log evidence assessment step to database.")

    def log_citation_verification(
        self,
        run_id: UUID | None,
        attempt: int,
        verification: object,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = getattr(verification, "llm_call", None)
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            mappings = []
            if hasattr(verification, "mappings") and verification.mappings:
                for m in verification.mappings:
                    if hasattr(m, "model_dump"):
                        mappings.append(m.model_dump())
                    else:
                        mappings.append({
                            "citation_id": getattr(m, "citation_id", None),
                            "supports_claim": getattr(m, "supports_claim", None),
                            "snippet_evidence": getattr(m, "snippet_evidence", None),
                        })

            step = PipelineStep(
                run_id=run_id,
                step_type="verify_citations",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={
                    "has_valid_citations": getattr(verification, "has_valid_citations", None),
                    "mappings": mappings,
                },
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log citation verification step to database.")

    def log_groundedness(
        self,
        run_id: UUID | None,
        attempt: int,
        groundedness: object,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            llm = getattr(groundedness, "llm_call", None)
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None

            prompt_tokens = getattr(llm, "prompt_tokens", None) if llm else None
            completion_tokens = getattr(llm, "completion_tokens", None) if llm else None
            cached_tokens = getattr(llm, "cached_tokens", None) if llm else None
            cost_usd = None
            if llm and (prompt_tokens or completion_tokens):
                from app.services.v5.cost_model import estimate_cost
                cost_usd = float(estimate_cost(llm.model_name, {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens
                }))

            step = PipelineStep(
                run_id=run_id,
                step_type="evaluate_groundedness",
                attempt=attempt,
                model_name=llm.model_name if llm else None,
                model_input=model_input,
                raw_thinking=llm.raw_thinking if llm else None,
                model_output=llm.content if llm else None,
                structured_output={
                    "score": getattr(groundedness, "score", None),
                    "reasoning": getattr(groundedness, "reasoning", None),
                    "is_grounded": getattr(groundedness, "is_grounded", None),
                },
                latency_ms=llm.latency_ms if llm else 0,
                status="success",
                created_at=datetime.now(UTC),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost_usd,
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log groundedness evaluation step to database.")

    def end_run(
        self,
        run_id: UUID | None,
        final_route: str,
        final_answer: str,
        final_confidence: float | None,
        attempts_count: int,
        disclaimer_appended: bool,
        total_cost_usd: float | None = None,
        total_tokens: int | None = None,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            run = self._session.get(PipelineRun, run_id)
            if run:
                run.end_time = datetime.now(UTC)
                run.final_route = str(final_route)
                run.final_answer = final_answer
                run.final_confidence = final_confidence
                run.attempts_count = attempts_count
                run.disclaimer_appended = disclaimer_appended
                if total_cost_usd is not None:
                    run.total_cost_usd = total_cost_usd
                if total_tokens is not None:
                    run.total_tokens = total_tokens
                self._session.add(run)
                self._session.commit()
        except Exception:
            logger.exception("Failed to log search pipeline run completion to database.")
            self._session.rollback()
