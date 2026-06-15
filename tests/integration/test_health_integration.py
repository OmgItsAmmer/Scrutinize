import pytest


@pytest.mark.integration
def test_health_endpoint_with_real_checks(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "scrutinize"
    assert set(payload["checks"]) >= {"database", "redis", "qdrant"}
