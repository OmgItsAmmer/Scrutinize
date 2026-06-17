"""Retry OpenAI calls on rate-limit (429) with backoff."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import TypeVar

from openai import APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRY_AFTER_MS = re.compile(r"try again in (\d+)ms", re.IGNORECASE)
_RETRY_AFTER_S = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


def _retry_delay_seconds(exc: RateLimitError, attempt: int, min_delay: float) -> float:
    message = str(exc)
    ms_match = _RETRY_AFTER_MS.search(message)
    if ms_match:
        return max(int(ms_match.group(1)) / 1000.0, min_delay)
    s_match = _RETRY_AFTER_S.search(message)
    if s_match:
        return max(float(s_match.group(1)), min_delay)
    return min(min_delay * (2**attempt), 60.0)


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int,
    min_delay_seconds: float,
    label: str = "openai",
) -> T:
    """Call *fn*, retrying transient OpenAI rate limits."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except RateLimitError as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = _retry_delay_seconds(exc, attempt, min_delay_seconds)
            logger.warning(
                "%s rate limited (attempt %d/%d); retrying in %.1fs",
                label,
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
        except APIStatusError as exc:
            if exc.status_code != 429 or attempt >= max_retries:
                raise
            last_exc = exc
            delay = min(min_delay_seconds * (2**attempt), 60.0)
            logger.warning(
                "%s returned 429 (attempt %d/%d); retrying in %.1fs",
                label,
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)

    assert last_exc is not None
    raise last_exc
