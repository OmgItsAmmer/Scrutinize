from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.schemas.v2.search import ChatMessage, ConversationState
from app.services.v2.decision_agent import DecisionResult
from app.services.v2.pipeline_orchestrator import (
    LOW_CONFIDENCE_DISCLAIMER,
    NO_INDEXED_CONTENT,
    PipelineOrchestrator,
)
from app.services.v2.query_rewriter import RewrittenQuery
from app.services.v2.rag_gate import GateResult


def _settings(**overrides: object) -> Settings:
    defaults = {
        "local_llm_base_url": "http://llm.test",
        "v2_max_pipeline_attempts": 2,
        "v2_confidence_threshold": 0.7,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _memory_mock() -> MagicMock:
    memory = MagicMock()
    memory.prepare.return_value = (ConversationState(), "")

    def _record(state: ConversationState, user: str, assistant: str) -> ConversationState:
        return ConversationState(
            messages=[
                *state.messages,
                ChatMessage(role="user", content=user),
                ChatMessage(role="assistant", content=assistant),
            ],
        )

    memory.record_exchange.side_effect = _record
    return memory


def _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory, **settings_overrides):
    return PipelineOrchestrator(
        rewriter,
        gate,
        generic,
        rrf,
        synthesis,
        decision,
        memory,
        _settings(**settings_overrides),
    )


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_rewrites_before_gate():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="hello greeting assistant")
    gate = MagicMock()
    gate.classify.return_value = GateResult(
        route="generic",
        reason="Greeting",
        reply="Hello!",
    )
    generic = MagicMock()
    rrf = MagicMock()
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="good",
        confidence=0.95,
        feedback="",
        correct_route="generic",
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    orchestrator.search("Hi there")

    rewriter.rewrite.assert_called_once()
    gate.classify.assert_called_once()
    _, gate_kwargs = gate.classify.call_args
    assert gate_kwargs.get("rewritten") == "hello greeting assistant"


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_generic_uses_decision_confidence():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="joke request humor")
    gate = MagicMock()
    gate.classify.return_value = GateResult(
        route="generic",
        reason="Chitchat",
        reply="Here is a joke.",
    )
    generic = MagicMock()
    rrf = MagicMock()
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="good",
        confidence=0.91,
        feedback="",
        correct_route="generic",
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("Tell me a joke")

    assert response.route == "generic"
    assert response.answer == "Here is a joke."
    assert response.confidence == 0.91
    decision.evaluate.assert_called_once()
    generic.reply.assert_not_called()
    rrf.retrieve.assert_not_called()


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_generic_escalates_to_rag_when_decision_says_so():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="garlic amount pasta recipe")
    gate = MagicMock()
    gate.classify.return_value = GateResult(
        route="generic",
        reason="Misclassified",
        reply="Maybe two cloves?",
    )
    generic = MagicMock()
    rrf = MagicMock()
    source = SearchSource(
        segment_id=uuid4(),
        file_id=uuid4(),
        modality=FileModality.TEXT,
        title="pasta.md",
        content="Use 2 cloves garlic.",
        source_path="https://example.com/pasta.md",
        score=0.9,
    )
    rrf.retrieve.return_value = [source]
    synthesis = MagicMock()
    synthesis.synthesize.return_value = "The recipe uses two cloves of garlic."
    decision = MagicMock()
    decision.evaluate.side_effect = [
        DecisionResult(
            verdict="retry",
            confidence=0.2,
            feedback="Cooking question needs library search.",
            correct_route="rag",
        ),
        DecisionResult(verdict="good", confidence=0.88, feedback="", correct_route="rag"),
    ]
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("How much garlic in the pasta recipe?")

    assert response.route == "rag"
    assert response.answer == "The recipe uses two cloves of garlic."
    assert decision.evaluate.call_count == 2
    rrf.retrieve.assert_called_once()


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_generic_fallback_calls_generic_agent():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="weather today")
    gate = MagicMock()
    gate.classify.return_value = GateResult(route="generic", reason="Chitchat", reply=None)
    generic = MagicMock()
    generic.reply.return_value = "Sure, I can help with that."
    rrf = MagicMock()
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="good",
        confidence=0.85,
        feedback="",
        correct_route="generic",
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("What's the weather?")

    assert response.answer == "Sure, I can help with that."
    generic.reply.assert_called_once()
    decision.evaluate.assert_called_once()


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_orchestrator_rag_with_synthesis():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="garlic amount pasta recipe")
    gate = MagicMock()
    gate.classify.return_value = GateResult(route="rag", reason="Cooking query")
    generic = MagicMock()
    rrf = MagicMock()
    source = SearchSource(
        segment_id=uuid4(),
        file_id=uuid4(),
        modality=FileModality.TEXT,
        title="pasta.md",
        content="Use 2 cloves garlic.",
        source_path="https://example.com/pasta.md",
        score=0.9,
    )
    rrf.retrieve.return_value = [source]
    synthesis = MagicMock()
    synthesis.synthesize.return_value = "The recipe uses two cloves of garlic."
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="good", confidence=0.88, feedback="", correct_route="rag"
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("How much garlic in the pasta recipe?")

    assert response.route == "rag"
    assert response.answer == "The recipe uses two cloves of garlic."
    assert response.rewritten_query == "garlic amount pasta recipe"
    decision.evaluate.assert_called_once()
    rewriter.rewrite.assert_called_once()


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_orchestrator_rag_empty_results():
    rewriter = MagicMock()
    rewriter.rewrite.return_value = RewrittenQuery(text="missing topic")
    gate = MagicMock()
    gate.classify.return_value = GateResult(route="rag", reason="Library query")
    generic = MagicMock()
    rrf = MagicMock()
    rrf.retrieve.return_value = []
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="good", confidence=0.75, feedback="", correct_route="rag"
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("What does the doc say about unicorns?")

    assert response.answer == NO_INDEXED_CONTENT
    synthesis.synthesize.assert_not_called()


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_orchestrator_retries_then_succeeds():
    rewriter = MagicMock()
    rewriter.rewrite.side_effect = [
        RewrittenQuery(text="vague garlic query"),
        RewrittenQuery(text="garlic cloves pasta recipe quantity"),
    ]
    gate = MagicMock()
    gate.classify.return_value = GateResult(route="rag", reason="Library query")
    generic = MagicMock()
    rrf = MagicMock()
    rrf.retrieve.return_value = []
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.side_effect = [
        DecisionResult(
            verdict="retry", confidence=0.4, feedback="Add recipe keywords.", correct_route="rag"
        ),
        DecisionResult(verdict="good", confidence=0.85, feedback="", correct_route="rag"),
    ]
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("garlic?")

    assert response.attempts == 2
    assert response.confidence == 0.85


@pytest.mark.unit
@pytest.mark.v2
def test_pipeline_orchestrator_fallback_disclaimer_after_max_attempts():
    rewriter = MagicMock()
    rewriter.rewrite.side_effect = [
        RewrittenQuery(text="weak query"),
        RewrittenQuery(text="weak query revised"),
    ]
    gate = MagicMock()
    gate.classify.return_value = GateResult(route="rag", reason="Library query")
    generic = MagicMock()
    rrf = MagicMock()
    rrf.retrieve.return_value = []
    synthesis = MagicMock()
    decision = MagicMock()
    decision.evaluate.return_value = DecisionResult(
        verdict="retry", confidence=0.2, feedback="Too vague.", correct_route="rag"
    )
    memory = _memory_mock()

    orchestrator = _orchestrator(rewriter, gate, generic, rrf, synthesis, decision, memory)
    response = orchestrator.search("something obscure")

    assert response.disclaimer_appended is True
    assert LOW_CONFIDENCE_DISCLAIMER in response.answer
