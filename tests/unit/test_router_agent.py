import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.services.agents.router_agent import RouterAgent


@pytest.mark.unit
def test_router_agent_parses_tool_call():
    settings = Settings(openai_api_key="test-key")
    agent = RouterAgent(settings)
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(
        {
            "search_query": "person drinking milk from a glass",
            "modality_filter": "video",
        }
    )
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(tool_calls=[tool_call]))]

    with patch.object(agent._client.chat.completions, "create", return_value=response):
        result = agent.route("Find the video where someone drinks milk")

    assert result.search_query == "person drinking milk from a glass"
    assert result.modality_filter == FileModality.VIDEO


@pytest.mark.unit
def test_router_agent_falls_back_to_raw_query_without_tool_call():
    settings = Settings(openai_api_key="test-key")
    agent = RouterAgent(settings)
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(tool_calls=[]))]

    with patch.object(agent._client.chat.completions, "create", return_value=response):
        result = agent.route("hello world")

    assert result.search_query == "hello world"
    assert result.modality_filter is None
