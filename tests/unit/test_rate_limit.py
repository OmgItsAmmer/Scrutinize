from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.core.rate_limit import (
    InMemoryRateLimitStore,
    RateLimiter,
    get_client_ip,
    reset_rate_limit_store,
    route_tier,
)


def _limiter(
    *,
    expensive: int = 3,
    general: int = 10,
    global_limit: int = 20,
) -> RateLimiter:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_expensive_requests=expensive,
        rate_limit_expensive_window_seconds=60,
        rate_limit_general_requests=general,
        rate_limit_general_window_seconds=60,
        rate_limit_global_requests=global_limit,
        rate_limit_global_window_seconds=60,
    )
    return RateLimiter(InMemoryRateLimitStore(), settings)


@pytest.mark.unit
def test_route_tier_classifies_expensive_endpoints():
    assert route_tier("POST", "/search") == "expensive"
    assert route_tier("POST", "/upload") == "expensive"
    assert route_tier("GET", "/library") == "general"
    assert route_tier("GET", "/health") == "exempt"


@pytest.mark.unit
def test_rate_limiter_allows_requests_under_limit():
    limiter = _limiter(expensive=3)
    for _ in range(3):
        result = limiter.check("1.2.3.4", "POST", "/search")
        assert result is not None
        assert result.allowed is True


@pytest.mark.unit
def test_rate_limiter_blocks_expensive_requests_over_limit():
    limiter = _limiter(expensive=2)
    limiter.check("1.2.3.4", "POST", "/search")
    limiter.check("1.2.3.4", "POST", "/search")
    blocked = limiter.check("1.2.3.4", "POST", "/search")
    assert blocked is not None
    assert blocked.allowed is False
    assert blocked.remaining == 0


@pytest.mark.unit
def test_rate_limiter_tracks_ips_separately():
    limiter = _limiter(expensive=1)
    assert limiter.check("1.2.3.4", "POST", "/search").allowed is True
    assert limiter.check("5.6.7.8", "POST", "/search").allowed is True
    assert limiter.check("1.2.3.4", "POST", "/search").allowed is False


@pytest.mark.unit
def test_rate_limiter_skips_health_checks():
    limiter = _limiter(general=1)
    assert limiter.check("1.2.3.4", "GET", "/health") is None


@pytest.mark.unit
def test_get_client_ip_prefers_forwarded_header():
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
    request.client = MagicMock(host="127.0.0.1")
    assert get_client_ip(request) == "203.0.113.1"


@pytest.mark.unit
def test_middleware_returns_429_when_limit_exceeded(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_GENERAL_REQUESTS", "1")
    reset_rate_limit_store()

    from app.core.config import get_settings

    get_settings.cache_clear()

    first = client.get("/library")
    assert first.status_code == 200

    second = client.get("/library")
    assert second.status_code == 429
    assert "Rate limit exceeded" in second.json()["detail"]
    assert second.headers.get("Retry-After")

    get_settings.cache_clear()
    reset_rate_limit_store()
