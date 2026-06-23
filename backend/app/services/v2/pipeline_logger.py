from datetime import UTC, datetime
import logging
from uuid import UUID

from sqlmodel import Session, select

from app.models.file import FileModality
from app.models.pipeline_log import (
    PipelineRun,
    PipelineStep,
    RetrievedSource,
    StepEvaluation,
    StepGate,
    StepRetrieval,
    StepRewrite,
    StepSynthesis,
)
from app.schemas.search import SearchSource

logger = logging.getLogger(__name__)


class PipelineLogger:
    """Helper class to log v2 search pipeline execution steps to a relational DB."""

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
                query=query,
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
        input_query: str,
        prev_feedback: str | None,
        rewritten_query: str,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            step = PipelineStep(
                run_id=run_id,
                step_type="rewrite",
                attempt=attempt,
                created_at=datetime.now(UTC),
            )
            self._session.add(step)
            self._session.commit()
            self._session.refresh(step)

            rewrite = StepRewrite(
                step_id=step.id,
                input_query=input_query,
                prev_feedback=prev_feedback,
                rewritten_query=rewritten_query,
            )
            self._session.add(rewrite)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log query rewrite step to database.")

    def log_gate(
        self,
        run_id: UUID | None,
        route: str,
        reason: str | None,
        reply: str | None,
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

            step = PipelineStep(
                run_id=run_id,
                step_type="gate",
                attempt=attempt,
                created_at=datetime.now(UTC),
            )
            self._session.add(step)
            self._session.commit()
            self._session.refresh(step)

            gate = StepGate(
                step_id=step.id,
                route=route,
                reason=reason,
                reply=reply,
            )
            self._session.add(gate)
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
            step = PipelineStep(
                run_id=run_id,
                step_type="retrieval",
                attempt=attempt,
                created_at=datetime.now(UTC),
            )
            self._session.add(step)
            self._session.commit()
            self._session.refresh(step)

            retrieval = StepRetrieval(
                step_id=step.id,
                query=query,
                rewritten_query=rewritten_query,
            )
            self._session.add(retrieval)
            self._session.commit()

            for rank, source in enumerate(sources, start=1):
                db_source = RetrievedSource(
                    step_id=step.id,
                    segment_id=source.segment_id,
                    file_id=source.file_id,
                    modality=source.modality,
                    title=source.title,
                    content=source.content,
                    source_path=source.source_path,
                    start_time=source.start_time,
                    end_time=source.end_time,
                    score=source.score,
                    rank=rank,
                )
                self._session.add(db_source)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log retrieval step and sources to database.")

    def log_synthesis(
        self,
        run_id: UUID | None,
        attempt: int,
        answer: str,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            step = PipelineStep(
                run_id=run_id,
                step_type="synthesis",
                attempt=attempt,
                created_at=datetime.now(UTC),
            )
            self._session.add(step)
            self._session.commit()
            self._session.refresh(step)

            synthesis = StepSynthesis(
                step_id=step.id,
                answer=answer,
            )
            self._session.add(synthesis)
            self._session.commit()
        except Exception:
            logger.exception("Failed to log synthesis step to database.")

    def log_evaluation(
        self,
        run_id: UUID | None,
        attempt: int,
        route: str,
        draft_answer: str,
        verdict: str,
        confidence: float,
        correct_route: str | None,
        feedback: str | None,
    ) -> None:
        if not self._session or not run_id:
            return

        try:
            step = PipelineStep(
                run_id=run_id,
                step_type="evaluation",
                attempt=attempt,
                created_at=datetime.now(UTC),
            )
            self._session.add(step)
            self._session.commit()
            self._session.refresh(step)

            eval_step = StepEvaluation(
                step_id=step.id,
                verdict=verdict,
                confidence=confidence,
                correct_route=correct_route,
                feedback=feedback,
            )
            self._session.add(eval_step)
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
