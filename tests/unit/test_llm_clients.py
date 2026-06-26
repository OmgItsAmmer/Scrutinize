from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.services.v2.llm_clients.base import LlmResponse
from app.services.v2.llm_clients.local import LocalLlmClient, LocalLlmError


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_endpoint_resolution():
    settings = Settings()
    settings.local_llm_base_url = "https://example.ngrok-free.app"
    settings.local_llm_gate_url = "https://gate.ngrok-free.app/v1/chat/completions"
    settings.local_llm_gate_model = "my-gate-model"
    
    client = LocalLlmClient(settings)
    
    # Custom gate model URL mapping
    assert client._get_url("my-gate-model") == "https://gate.ngrok-free.app/v1/chat/completions"
    # Fallback default URL mapping
    assert client._get_url("other-model") == "https://example.ngrok-free.app/v1/chat/completions"


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_generate_success():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello user!",
                    "reasoning_content": "Thinking process details...",
                }
            }
        ]
    }

    with patch("app.services.v2.llm_clients.local.httpx.post", return_value=mock_response) as post:
        resp = client.generate("qwen3.5:0.8b", "You are helpful.", "Hi")

    assert isinstance(resp, LlmResponse)
    assert resp.content == "Hello user!"
    assert resp.model_name == "qwen3.5:0.8b"
    assert resp.prompt_system == "You are helpful."
    assert resp.prompt_user == "Hi"
    assert resp.raw_thinking == "Thinking process details..."
    assert resp.latency_ms >= 0

    post.assert_called_once()
    call_kwargs = post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "qwen3.5:0.8b"
    assert call_kwargs["json"]["messages"] == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    assert call_kwargs["json"]["stream"] is False
    assert call_kwargs["headers"]["ngrok-skip-browser-warning"] == "true"


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_json_mode():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"route":"rag"}',
                }
            }
        ]
    }

    with patch("app.services.v2.llm_clients.local.httpx.post", return_value=mock_response) as post:
        resp = client.generate("qwen3.5:0.8b", "Return JSON.", "classify", json_mode=True)

    assert resp.content == '{"route":"rag"}'
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_empty_response_raises():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "   ",
                }
            }
        ]
    }

    with (
        patch("app.services.v2.llm_clients.local.httpx.post", return_value=mock_response),
        pytest.raises(LocalLlmError, match="empty response"),
    ):
        client.generate("qwen3.5:0.8b", "", "ping")


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_http_error():
    settings = get_settings()
    client = LocalLlmClient(settings)
    url = client._get_url("qwen3.5:0.8b")

    request = httpx.Request("POST", url)
    response = httpx.Response(502, request=request)

    with (
        patch(
            "app.services.v2.llm_clients.local.httpx.post",
            side_effect=httpx.HTTPStatusError("bad gateway", request=request, response=response),
        ),
        pytest.raises(LocalLlmError, match="HTTP 502"),
    ):
        client.generate("qwen3.5:0.8b", "", "ping")


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_requires_base_url(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_GATE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_REWRITER_URL", "")
    monkeypatch.setenv("LOCAL_LLM_DECISION_URL", "")
    get_settings.cache_clear()

    settings = get_settings()
    # Explicitly verify configuration check
    with pytest.raises(RuntimeError, match="local LLM URL is required"):
        LocalLlmClient(settings)

    get_settings.cache_clear()
