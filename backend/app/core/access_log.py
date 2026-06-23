import logging

# Uvicorn access lines: 127.0.0.1:64797 - "GET /status/... HTTP/1.1" 200 OK
_QUIET_FRAGMENTS = ('"GET /health', '"GET /status/')


class QuietPollAccessLogFilter(logging.Filter):
    """Drop routine health/status poll lines from uvicorn access logs in dev."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(fragment in message for fragment in _QUIET_FRAGMENTS)


def quiet_poll_access_logs() -> None:
    logging.getLogger("uvicorn.access").addFilter(QuietPollAccessLogFilter())
