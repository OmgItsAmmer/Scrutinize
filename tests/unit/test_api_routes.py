import pytest


@pytest.mark.unit
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "scrutinize"
    assert "checks" in body


@pytest.mark.unit
def test_health_wake_endpoint(client):
    response = client.get("/health/wake")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "scrutinize"
    assert body["checks"] == {}


@pytest.mark.unit
def test_job_status_not_found(client):
    from uuid import uuid4

    response = client.get(f"/status/{uuid4()}")
    assert response.status_code == 404
