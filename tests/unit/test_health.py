from unittest.mock import patch

import pytest

from app.schemas.health import DependencyCheck


@pytest.mark.unit
def test_build_health_response_ok(session):
    from app.core.config import get_settings
    from app.services.health import build_health_response

    settings = get_settings()
    with (
        patch("app.services.health.check_database", return_value=DependencyCheck(status="ok")),
        patch("app.services.health.check_redis", return_value=DependencyCheck(status="ok")),
        patch("app.services.health.check_qdrant", return_value=DependencyCheck(status="ok")),
    ):
        response = build_health_response(settings, session, version="0.1.0")

    assert response.status == "ok"
    assert response.service == "scrutinize"
    assert response.checks["database"].status == "ok"


@pytest.mark.unit
def test_build_health_response_degraded(session):
    from app.core.config import get_settings
    from app.services.health import build_health_response

    settings = get_settings()
    with (
        patch("app.services.health.check_database", return_value=DependencyCheck(status="ok")),
        patch(
            "app.services.health.check_redis",
            return_value=DependencyCheck(status="error", detail="connection refused"),
        ),
        patch("app.services.health.check_qdrant", return_value=DependencyCheck(status="ok")),
    ):
        response = build_health_response(settings, session, version="0.1.0")

    assert response.status == "degraded"
    assert response.checks["redis"].status == "error"
