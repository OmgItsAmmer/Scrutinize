import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.services.v2.local_llm_client import LlmResponse
from app.services.v2.decision_agent import DecisionAgent, DecisionContext


@pytest.mark.unit
@pytest.mark.v2
def test_decision_agent_parses_json():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps(
            {"verdict": "good", "confidence": 0.92, "feedback": "Well grounded."}
        ),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    agent = DecisionAgent(client, settings)

    result = agent.evaluate(
        DecisionContext(
            original_query="How much garlic?",
            rewritten_query="garlic quantity recipe",
            route="rag",
            draft_answer="Two cloves.",
            sources=[],
            attempt=1,
        )
    )

    assert result.verdict == "good"
    assert result.confidence == 0.92
    assert result.correct_route is None
    assert client.generate.call_args.args[0] == settings.local_llm_decision_model


@pytest.mark.unit
@pytest.mark.v2
def test_decision_agent_includes_chunk_summaries():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps(
            {
                "verdict": "retry",
                "confidence": 0.2,
                "feedback": "Cooking question — search library.",
                "correct_route": "rag",
            }
        ),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    agent = DecisionAgent(client, settings)
    source = SearchSource(
        segment_id=uuid4(),
        file_id=uuid4(),
        modality=FileModality.TEXT,
        title="pasta.md",
        content="Use 2 cloves garlic.",
        source_path="https://example.com/pasta.md",
        score=0.8,
    )

    agent.evaluate(
        DecisionContext(
            original_query="garlic?",
            rewritten_query="garlic recipe",
            route="rag",
            draft_answer="Maybe one clove.",
            sources=[source],
            attempt=2,
        )
    )

    user_prompt = client.generate.call_args.args[2]
    assert "pasta.md" in user_prompt
    assert "Attempt: 2" in user_prompt


@pytest.mark.unit
@pytest.mark.v2
def test_decision_agent_parses_correct_route():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps(
            {
                "verdict": "retry",
                "confidence": 0.3,
                "feedback": "Needs RAG.",
                "correct_route": "rag",
            }
        ),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    agent = DecisionAgent(client, settings)

    result = agent.evaluate(
        DecisionContext(
            original_query="garlic in recipe?",
            rewritten_query="garlic recipe quantity",
            route="generic",
            draft_answer="Maybe one clove.",
            sources=[],
            attempt=1,
        )
    )

    assert result.correct_route == "rag"


@pytest.mark.unit
@pytest.mark.v2
def test_decision_agent_parse_failure_defaults_to_retry():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="not-json",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    agent = DecisionAgent(client, settings)

    result = agent.evaluate(
        DecisionContext(
            original_query="hello",
            rewritten_query="hello",
            route="generic",
            draft_answer="Hi!",
            sources=[],
            attempt=1,
        )
    )

    assert result.verdict == "retry"
    assert result.confidence == 0.0
