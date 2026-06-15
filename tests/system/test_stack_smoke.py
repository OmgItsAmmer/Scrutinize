import os

import httpx
import pytest


@pytest.mark.system
def test_stack_health_endpoint(api_base_url: str):
    if os.getenv("CI") != "true" and os.getenv("RUN_SYSTEM_TESTS") != "1":
        pytest.skip("Set RUN_SYSTEM_TESTS=1 or run inside CI with docker compose up")

    response = httpx.get(f"{api_base_url.rstrip('/')}/health", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "scrutinize"
