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
    ) -> UUID | None:
        if not self._session:
            return None

        try:
            run = PipelineRun(
                original_query=query,
                modality_filter=modality_filter,
                conversation_context=conversation_context,
                start_time=datetime.now(UTC),
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
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log query rewrite step to database.")

    def log_gate(
        self,
        run_id: UUID | None,
        gate_result: GateResult,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            statement = select(PipelineStep).where(
                PipelineStep.run_id == run_id,
                PipelineStep.step_type == "gate",
            )
            existing_gates = self._session.exec(statement).all()
            attempt = len(existing_gates) + 1

            llm = gate_result.llm_call
            model_input = {"system": llm.prompt_system, "user": llm.prompt_user} if llm else None
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
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            serialized_sources = []
            for rank, source in enumerate(sources, start=1):
                serialized_sources.append({
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
                })

            step = PipelineStep(
                run_id=run_id,
                step_type="retrieval",
                attempt=attempt,
                model_name=None,
                model_input=None,
                raw_thinking=None,
                model_output=None,
                structured_output={
                    "query": query,
                    "rewritten_query": rewritten_query,
                },
                retrieved_sources=serialized_sources,
                latency_ms=0,
                status="success",
                created_at=datetime.now(UTC),
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
            )
            self._session.add(step)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log evaluation step to database.")

    def end_run(
        self,
        run_id: UUID | None,
        final_route: str,
        final_answer: str,
        final_confidence: float | None,
        attempts_count: int,
        disclaimer_appended: bool,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            run = self._session.get(PipelineRun, run_id)
            if run:
                run.end_time = datetime.now(UTC)
                run.final_route = final_route
                run.final_answer = final_answer
                run.final_confidence = final_confidence
                run.attempts_count = attempts_count
                run.disclaimer_appended = disclaimer_appended
                self._session.add(run)
                self._session.commit()
        except Exception:
            logger.exception("Failed to log search pipeline run completion to database.")
