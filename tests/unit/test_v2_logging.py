from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.models.file import FileModality
from app.models.pipeline_log import PipelineRun, PipelineStep
from app.schemas.search import SearchSource
from app.services.v2.local_llm_client import LlmResponse
from app.services.v2.query_rewriter import RewrittenQuery
from app.services.v2.rag_gate import GateResult
from app.services.v2.rag_synthesis_agent import SynthesisResult
from app.services.v2.decision_agent import DecisionResult
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
    assert run.original_query == "What is the weather?"
    assert run.modality_filter is None
    assert run.conversation_context == "Context 123"
    assert run.start_time is not None
    assert run.end_time is None

    # 2. Log Rewrite
    llm_rewrite = LlmResponse(
        content="current weather query",
        model_name="qwen-rewriter",
        prompt_system="Rewrite query:",
        prompt_user="What is the weather?",
        raw_thinking="Need to rewrite weather query",
        latency_ms=150,
    )
    db_logger.log_rewrite(
        run_id=run_id,
        attempt=1,
        rewritten=RewrittenQuery(text="current weather query", llm_call=llm_rewrite),
    )

    steps = session.exec(select(PipelineStep).where(PipelineStep.run_id == run_id)).all()
    assert len(steps) == 1
    assert steps[0].step_type == "rewrite"
    assert steps[0].attempt == 1
    assert steps[0].model_name == "qwen-rewriter"
    assert steps[0].model_input == {"system": "Rewrite query:", "user": "What is the weather?"}
    assert steps[0].raw_thinking == "Need to rewrite weather query"
    assert steps[0].model_output == "current weather query"
    assert steps[0].structured_output == {"rewritten_query": "current weather query"}
    assert steps[0].latency_ms == 150
    assert steps[0].status == "success"

    # 3. Log Gate
    llm_gate = LlmResponse(
        content='{"route": "generic", "reason": "Chitchat request", "reply": "Hello there!"}',
        model_name="qwen-gate",
        prompt_system="System gate",
        prompt_user="What is the weather?",
        raw_thinking=None,
        latency_ms=200,
    )
    db_logger.log_gate(
        run_id=run_id,
        gate_result=GateResult(
            route="generic",
            reason="Chitchat request",
            reply="Hello there!",
            llm_call=llm_gate,
        ),
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 2
    assert steps[1].step_type == "gate"
    assert steps[1].attempt == 1
    assert steps[1].model_name == "qwen-gate"
    assert steps[1].structured_output == {
        "route": "generic",
        "reason": "Chitchat request",
        "reply": "Hello there!",
    }

    # 4. Log Gate Escalation (Attempt 2)
    db_logger.log_gate(
        run_id=run_id,
        gate_result=GateResult(
            route="rag",
            reason="Escalated from generic",
            reply=None,
            llm_call=None,
        ),
    )
    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 3
    assert steps[2].step_type == "gate"
    assert steps[2].attempt == 2
    assert steps[2].model_name is None
    assert steps[2].structured_output == {
        "route": "rag",
        "reason": "Escalated from generic",
        "reply": None,
    }

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
    assert steps[3].retrieved_sources is not None
    assert len(steps[3].retrieved_sources) == 1
    assert steps[3].retrieved_sources[0]["segment_id"] == str(segment_id)
    assert steps[3].retrieved_sources[0]["file_id"] == str(file_id)
    assert steps[3].retrieved_sources[0]["content"] == "sunny weather predicted today."
    assert steps[3].retrieved_sources[0]["score"] == 0.95
    assert steps[3].retrieved_sources[0]["rank"] == 1

    # 6. Log Synthesis
    llm_synthesis = LlmResponse(
        content="The weather is sunny.",
        model_name="qwen-synthesis",
        prompt_system="System synth",
        prompt_user="Context...",
        raw_thinking=None,
        latency_ms=300,
    )
    db_logger.log_synthesis(
        run_id=run_id,
        attempt=1,
        synthesis_result=SynthesisResult(
            answer="The weather is sunny.",
            llm_call=llm_synthesis,
        ),
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 5
    assert steps[4].step_type == "synthesis"
    assert steps[4].attempt == 1
    assert steps[4].model_name == "qwen-synthesis"
    assert steps[4].structured_output == {"answer": "The weather is sunny."}

    # 7. Log Evaluation
    llm_eval = LlmResponse(
        content='{"verdict": "good", "confidence": 0.98, "feedback": "", "correct_route": "rag"}',
        model_name="qwen-eval",
        prompt_system="System eval",
        prompt_user="Evaluate...",
        raw_thinking=None,
        latency_ms=250,
    )
    db_logger.log_evaluation(
        run_id=run_id,
        attempt=1,
        decision=DecisionResult(
            verdict="good",
            confidence=0.98,
            feedback="",
            correct_route="rag",
            llm_call=llm_eval,
        ),
    )

    steps = session.exec(
        select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.created_at)
    ).all()
    assert len(steps) == 6
    assert steps[5].step_type == "evaluation"
    assert steps[5].attempt == 1
    assert steps[5].model_name == "qwen-eval"
    assert steps[5].structured_output == {
        "verdict": "good",
        "confidence": 0.98,
        "feedback": "",
        "correct_route": "rag",
    }

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
