import pytest
from openai import RateLimitError

from app.services.openai_retry import call_with_retry


class _FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}
        self.http_version = "HTTP/1.1"
        self.reason_phrase = "Too Many Requests"
        self.request = None
        self.is_closed = True
        self.is_stream_consumed = True


@pytest.mark.unit
def test_call_with_retry_waits_and_retries_on_rate_limit(monkeypatch):
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RateLimitError(
                "rate limit",
                response=_FakeResponse(429, "try again in 10ms"),
                body=None,
            )
        return "ok"

    slept: list[float] = []
    monkeypatch.setattr("app.services.openai_retry.time.sleep", lambda s: slept.append(s))
    result = call_with_retry(flaky, max_retries=2, min_delay_seconds=0.5, label="test")

    assert result == "ok"
    assert attempts["count"] == 2
    assert slept == [0.5]
