from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.services.v2.local_llm_client import LocalLlmClient, LocalLlmError


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_generate_success():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "hello from qwen"}

    with patch("app.services.v2.local_llm_client.httpx.post", return_value=mock_response) as post:
        text = client.generate("qwen3.5:0.8b", "You are helpful.", "Hi")

    assert text == "hello from qwen"
    post.assert_called_once()
    call_kwargs = post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "qwen3.5:0.8b"
    assert call_kwargs["json"]["prompt"] == "Hi"
    assert call_kwargs["json"]["system"] == "You are helpful."
    assert call_kwargs["json"]["stream"] is False
    assert call_kwargs["headers"]["ngrok-skip-browser-warning"] == "true"
    assert client.generate_url == "http://local-llm.test/api/generate"


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_json_mode():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": '{"route":"rag"}'}

    with patch("app.services.v2.local_llm_client.httpx.post", return_value=mock_response) as post:
        text = client.generate("qwen3.5:0.8b", "Return JSON.", "classify", json_mode=True)

    assert text == '{"route":"rag"}'
    assert post.call_args.kwargs["json"]["format"] == "json"


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_empty_response_raises():
    settings = get_settings()
    client = LocalLlmClient(settings)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "  "}

    with (
        patch("app.services.v2.local_llm_client.httpx.post", return_value=mock_response),
        pytest.raises(LocalLlmError, match="empty response"),
    ):
        client.generate("qwen3.5:0.8b", "", "ping")


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_http_error():
    settings = get_settings()
    client = LocalLlmClient(settings)

    request = httpx.Request("POST", client.generate_url)
    response = httpx.Response(502, request=request)

    with (
        patch(
            "app.services.v2.local_llm_client.httpx.post",
            side_effect=httpx.HTTPStatusError("bad gateway", request=request, response=response),
        ),
        pytest.raises(LocalLlmError, match="HTTP 502"),
    ):
        client.generate("qwen3.5:0.8b", "", "ping")


@pytest.mark.unit
@pytest.mark.v2
def test_local_llm_client_requires_base_url(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    get_settings.cache_clear()

    settings = get_settings()
    with pytest.raises(RuntimeError, match="LOCAL_LLM_BASE_URL"):
        LocalLlmClient(settings)

    get_settings.cache_clear()
