from uuid import uuid4

import pytest
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
from app.services.v2.pipeline_logger import PipelineLogger


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_logger_full_flow(session: Session):
    db_logger = PipelineLogger(session)

    # 1. Start Run
    run_id = db_logger.start_run(
        query="What is the weather?",
        modality_filter=None,
        conversation_context="Context 123",
    )
    assert run_id is not None

    run = session.get(PipelineRun, run_id)
    assert run is not None
    assert run.query == "What is the weather?"
    assert run.modality_filter is None
    assert run.conversation_context == "Context 123"
    assert run.start_time is not None
    assert run.end_time is None

    # 2. Log Rewrite
    db_logger.log_rewrite(
        run_id=run_id,
        attempt=1,
        input_query="What is the weather?",
        prev_feedback=None,
        rewritten_query="current weather query",
    )

    steps = session.exec(select(PipelineStep).where(PipelineStep.run_id == run_id)).all()
    assert len(steps) == 1
    assert steps[0].step_type == "rewrite"
    assert steps[0].attempt == 1

    rewrite = session.get(StepRewrite, steps[0].id)
    assert rewrite is not None
    assert rewrite.input_query == "What is the weather?"
    assert rewrite.rewritten_query == "current weather query"
    assert rewrite.prev_feedback is None

    # 3. Log Gate
    db_logger.log_gate(
        run_id=run_id,
        route="generic",
        reason="Chitchat request",
        reply="Hello there!",
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 2
    assert steps[1].step_type == "gate"
    assert steps[1].attempt == 1

    gate = session.get(StepGate, steps[1].id)
    assert gate is not None
    assert gate.route == "generic"
    assert gate.reason == "Chitchat request"
    assert gate.reply == "Hello there!"

    # 4. Log Gate Escalation (Attempt 2)
    db_logger.log_gate(
        run_id=run_id,
        route="rag",
        reason="Escalated from generic",
        reply=None,
    )
    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 3
    assert steps[2].step_type == "gate"
    assert steps[2].attempt == 2

    gate2 = session.get(StepGate, steps[2].id)
    assert gate2 is not None
    assert gate2.route == "rag"
    assert gate2.reason == "Escalated from generic"
    assert gate2.reply is None

    # 5. Log Retrieval
    segment_id = uuid4()
    file_id = uuid4()
    sources = [
        SearchSource(
            segment_id=segment_id,
            file_id=file_id,
            modality=FileModality.TEXT,
            title="doc.txt",
            content="sunny weather predicted today.",
            source_path="/path/to/doc.txt",
            score=0.95,
        )
    ]
    db_logger.log_retrieval(
        run_id=run_id,
        attempt=1,
        query="What is the weather?",
        rewritten_query="current weather query",
        sources=sources,
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 4
    assert steps[3].step_type == "retrieval"
    assert steps[3].attempt == 1

    retrieval = session.get(StepRetrieval, steps[3].id)
    assert retrieval is not None
    assert retrieval.query == "What is the weather?"
    assert retrieval.rewritten_query == "current weather query"

    db_sources = session.exec(
        select(RetrievedSource).where(RetrievedSource.step_id == steps[3].id)
    ).all()
    assert len(db_sources) == 1
    assert db_sources[0].segment_id == segment_id
    assert db_sources[0].file_id == file_id
    assert db_sources[0].content == "sunny weather predicted today."
    assert db_sources[0].score == 0.95
    assert db_sources[0].rank == 1

    # 6. Log Synthesis
    db_logger.log_synthesis(
        run_id=run_id,
        attempt=1,
        answer="The weather is sunny.",
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 5
    assert steps[4].step_type == "synthesis"

    synthesis = session.get(StepSynthesis, steps[4].id)
    assert synthesis is not None
    assert synthesis.answer == "The weather is sunny."

    # 7. Log Evaluation
    db_logger.log_evaluation(
        run_id=run_id,
        attempt=1,
        route="rag",
        draft_answer="The weather is sunny.",
        verdict="good",
        confidence=0.98,
        correct_route="rag",
        feedback=None,
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 6
    assert steps[5].step_type == "evaluation"

    evaluation = session.get(StepEvaluation, steps[5].id)
    assert evaluation is not None
    assert evaluation.verdict == "good"
    assert evaluation.confidence == 0.98
    assert evaluation.correct_route == "rag"
    assert evaluation.feedback is None

    # 8. End Run
    db_logger.end_run(
        run_id=run_id,
        final_route="rag",
        final_answer="The weather is sunny.",
        final_confidence=0.98,
        attempts_count=1,
        disclaimer_appended=False,
    )

    session.refresh(run)
    assert run.end_time is not None
    assert run.final_route == "rag"
    assert run.final_answer == "The weather is sunny."
    assert run.final_confidence == 0.98
    assert run.attempts_count == 1
    assert run.disclaimer_appended is False
