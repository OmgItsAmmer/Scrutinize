from unittest.mock import MagicMock
import pydantic_ai
from app.core.config import Settings
from app.schemas.v4.rag import GateResult
from app.services.v4.rag_gate import RagGate
from app.services.v4.burr_orchestrator import BurrOrchestrator


def test_v4_rag_gate_classify(monkeypatch):
    mock_run_result = MagicMock()
    mock_run_result.data = GateResult(
        route="rag",
        reason="Needs project data.",
        requested_tool="generate_pdf",
        reply=None,
    )

    # Mock pydantic_ai.Agent.run_sync
    monkeypatch.setattr(pydantic_ai.Agent, "run_sync", lambda self, prompt: mock_run_result)

    settings = Settings()
    settings.local_llm_base_url = "http://mock"
    settings.local_llm_gate_model = "fake-model"
    settings.local_llm_gate_url = "http://mock"

    gate = RagGate(settings)
    res = gate.classify("Hello")

    assert res.route == "rag"
    assert res.reason == "Needs project data."
    assert res.requested_tool == "generate_pdf"
    assert res.reply is None


def test_burr_orchestrator_build():
    # Mock dependencies
    rewriter = MagicMock()
    gate = MagicMock()
    generic_agent = MagicMock()
    rrf_retriever = MagicMock()
    rag_synthesis = MagicMock()
    decision_agent = MagicMock()
    conversation_memory = MagicMock()
    settings = MagicMock()
    settings.v2_confidence_threshold = 0.7

    orchestrator = BurrOrchestrator(
        rewriter=rewriter,
        gate=gate,
        generic_agent=generic_agent,
        rrf_retriever=rrf_retriever,
        rag_synthesis=rag_synthesis,
        decision_agent=decision_agent,
        conversation_memory=conversation_memory,
        settings=settings,
    )

    initial_state = {
        "query": "test query",
        "conversation_context": "",
        "client_requested_tool": None,
        "has_corpus": True,
        "use_cloud_llm": False,
        "route": None,
        "gate_result": None,
        "rewritten_query": "test query",
        "sources": [],
        "answer": "",
        "verdict": "good",
        "confidence": 1.0,
        "attempt": 1,
        "max_attempts": 2,
        "prev_feedback": None,
        "project_ctx": None,
        "project_id": None,
        "conversation_id": None,
        "modality_filter": None,
    }

    app = orchestrator.build_application(initial_state)
    assert app is not None
    # Verify the starting state and entrypoint
    assert app.get_next_action().name == "precheck"


def test_run_budget_controller_validation():
    import pytest
    from app.services.v4.run_budget import RunBudget, BudgetExceededError

    # Safe state
    budget = RunBudget(
        attempts=1,
        llm_calls=5,
        web_searches=1,
        tools=2,
        input_tokens=15000,
    )
    budget.check()  # should not raise

    # Too many attempts
    with pytest.raises(BudgetExceededError) as exc_info:
        RunBudget(attempts=3).check()
    assert "Attempts count" in str(exc_info.value)

    # Too many LLM calls
    with pytest.raises(BudgetExceededError) as exc_info:
        RunBudget(llm_calls=7).check()
    assert "LLM calls count" in str(exc_info.value)

    # Too many web searches
    with pytest.raises(BudgetExceededError) as exc_info:
        RunBudget(web_searches=3).check()
    assert "Web search count" in str(exc_info.value)

    # Too many tools
    with pytest.raises(BudgetExceededError) as exc_info:
        RunBudget(tools=4).check()
    assert "Tool execution count" in str(exc_info.value)

    # Too many input tokens
    with pytest.raises(BudgetExceededError) as exc_info:
        RunBudget(input_tokens=25000).check()
    assert "Input tokens count" in str(exc_info.value)

