from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.v2
def test_v2_llm_health_ok(client):
    with patch(
        "app.api.v2.llm_health.LocalLlmClient.generate",
        return_value="ok",
    ):
        response = client.get("/v2/llm-health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == "qwen3.5:0.8b"
    assert body["sample_response"] == "ok"


@pytest.mark.unit
@pytest.mark.v2
def test_v2_llm_health_error(client):
    from app.services.v2.local_llm_client import LocalLlmError

    with patch(
        "app.api.v2.llm_health.LocalLlmClient.generate",
        side_effect=LocalLlmError("Local LLM request timed out after 120s"),
    ):
        response = client.get("/v2/llm-health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "timed out" in body["detail"]


@pytest.mark.unit
@pytest.mark.v2
def test_v2_llm_health_not_configured(client, monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    response = client.get("/v2/llm-health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "not configured" in body["detail"].lower()

    get_settings.cache_clear()
