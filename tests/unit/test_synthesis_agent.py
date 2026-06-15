from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.services.agents.synthesis_agent import SynthesisAgent


@pytest.mark.unit
def test_synthesis_agent_returns_answer():
    settings = Settings(openai_api_key="test-key")
    agent = SynthesisAgent(settings)
    sources = [
        SearchSource(
            segment_id=uuid4(),
            file_id=uuid4(),
            modality=FileModality.VIDEO,
            title="bbq-day.mp4",
            content="Visual: A person drinks milk",
            source_path="https://example.com/bbq-day.mp4",
            start_time=42.0,
            end_time=51.0,
            score=0.91,
        )
    ]
    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content="See bbq-day.mp4 around 00:42."))
    ]

    with patch.object(agent._client.chat.completions, "create", return_value=response):
        answer = agent.synthesize("Find the video where someone drinks milk", sources)

    assert "bbq-day.mp4" in answer


@pytest.mark.unit
def test_synthesis_agent_handles_no_sources():
    settings = Settings(openai_api_key="test-key")
    agent = SynthesisAgent(settings)
    answer = agent.synthesize("anything", [])
    assert "No matching" in answer
