from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.services.v2.llm_clients.base import LlmResponse
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent


@pytest.mark.unit
@pytest.mark.v2
def test_rag_synthesis_agent_calls_local_llm():
    settings = Settings(local_llm_base_url="http://llm.test")
    client = MagicMock()
    client.generate.return_value = LlmResponse(
        content="The recipe uses two cloves of garlic.",
        model_name="model",
        prompt_system="sys",
        prompt_user="usr",
    )
    agent = RagSynthesisAgent(client, settings)

    sources = [
        SearchSource(
            segment_id=uuid4(),
            file_id=uuid4(),
            modality=FileModality.TEXT,
            title="pasta.md",
            content="Use 2 cloves garlic.",
            source_path="https://example.com/pasta.md",
            score=0.82,
        )
    ]

    result = agent.synthesize("How much garlic?", sources)

    assert result.answer == "The recipe uses two cloves of garlic."
    assert result.llm_call is not None
    assert result.llm_call.content == "The recipe uses two cloves of garlic."
    client.generate.assert_called_once()
    user_prompt = client.generate.call_args.args[2]
    assert "How much garlic?" in user_prompt
    assert "pasta.md" in user_prompt
