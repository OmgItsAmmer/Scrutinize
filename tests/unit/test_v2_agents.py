import json
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services.v2.json_utils import parse_json_object
from app.services.v2.llm_clients.base import LlmResponse
from app.services.v2.query_rewriter import QueryRewriter
from app.services.v2.rag_gate import RagGate


@pytest.mark.unit
@pytest.mark.v2
def test_parse_json_object_plain():
    data = parse_json_object('{"route": "rag", "reason": "library question"}')
    assert data["route"] == "rag"


@pytest.mark.unit
@pytest.mark.v2
def test_parse_json_object_fenced():
    raw = '```json\n{"route": "generic", "reason": "greeting"}\n```'
    data = parse_json_object(raw)
    assert data["route"] == "generic"


@pytest.mark.unit
@pytest.mark.v2
def test_query_rewriter_returns_rewritten_text():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="project plan milestones and deadlines",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    rewriter = QueryRewriter(client, settings)

    result = rewriter.rewrite("What does the plan say?")

    assert result.text == "project plan milestones and deadlines"
    assert result.llm_call is not None
    assert result.llm_call.content == "project plan milestones and deadlines"
    client.generate.assert_called_once()
    assert settings.local_llm_rewriter_model in client.generate.call_args.args


@pytest.mark.unit
@pytest.mark.v2
def test_query_rewriter_includes_feedback():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="video person drinking milk glass",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    rewriter = QueryRewriter(client, settings)

    rewriter.rewrite("Find milk video", feedback="Focus on video modality")

    user_prompt = client.generate.call_args.args[2]
    assert "Revision feedback" in user_prompt
    assert "video modality" in user_prompt


@pytest.mark.unit
@pytest.mark.v2
def test_query_rewriter_falls_back_to_original_on_empty():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="   ",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    rewriter = QueryRewriter(client, settings)

    result = rewriter.rewrite("hello")

    assert result.text == "hello"


@pytest.mark.unit
@pytest.mark.v2
def test_rag_gate_parses_json_route():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps(
            {
                "route": "generic",
                "reason": "General knowledge question",
                "reply": "Python is a programming language.",
            }
        ),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    gate = RagGate(client, settings)

    result = gate.classify("What is Python?")

    assert result.route == "generic"
    assert result.reply == "Python is a programming language."
    assert client.generate.call_args.kwargs.get("json_mode") is True


@pytest.mark.unit
@pytest.mark.v2
def test_rag_gate_routes_cooking_to_rag():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps(
            {
                "route": "rag",
                "reason": "Question about recipe ingredients",
                "reply": None,
            }
        ),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    gate = RagGate(client, settings)

    result = gate.classify("How much garlic in the pasta recipe?")

    assert result.route == "rag"
    assert result.reply is None


@pytest.mark.unit
@pytest.mark.v2
def test_rag_gate_defaults_to_generic_on_bad_json():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="not json at all",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    gate = RagGate(client, settings)

    result = gate.classify("Find my video")

    assert result.route == "generic"
    assert "failed" in result.reason.lower()


@pytest.mark.unit
@pytest.mark.v2
def test_rag_gate_unknown_route_defaults_to_generic():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content=json.dumps({"route": "maybe", "reason": "unclear"}),
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    gate = RagGate(client, settings)

    result = gate.classify("hello")

    assert result.route == "generic"
