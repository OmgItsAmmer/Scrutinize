"""Per-IP rate limiting backed by Redis (in-memory fallback when Redis is unavailable)."""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

EXPENSIVE_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/search"),
        ("POST", "/upload"),
    }
)


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int


class RateLimitStore(ABC):
    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> int:
        """Return the request count for the current window."""


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    def increment(self, key: str, window_seconds: int) -> int:
        window_id = int(time.time()) // window_seconds
        bucket_key = f"{key}:{window_id}"
        count = self._redis.incr(bucket_key)
        if count == 1:
            self._redis.expire(bucket_key, window_seconds + 1)
        return count


class InMemoryRateLimitStore(RateLimitStore):
    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def increment(self, key: str, window_seconds: int) -> int:
        window_id = int(time.time()) // window_seconds
        bucket_key = f"{key}:{window_id}"
        with self._lock:
            stored_window, count = self._counts.get(bucket_key, (window_id, 0))
            if stored_window != window_id:
                count = 0
            count += 1
            self._counts[bucket_key] = (window_id, count)
            return count


_store: RateLimitStore | None = None
_store_lock = threading.Lock()


def get_rate_limit_store(settings: Settings | None = None) -> RateLimitStore:
    global _store
    if _store is not None:
        return _store

    with _store_lock:
        if _store is not None:
            return _store

        cfg = settings or get_settings()
        try:
            redis_store = RedisRateLimitStore(cfg.redis_url)
            redis_store._redis.ping()
            _store = redis_store
            logger.info("Rate limiting using Redis at %s", cfg.redis_url)
        except (RedisError, OSError) as exc:
            logger.warning(
                "Redis unavailable for rate limiting (%s); using in-memory store",
                exc,
            )
            _store = InMemoryRateLimitStore()
        return _store


def reset_rate_limit_store() -> None:
    """Clear cached store (for tests)."""
    global _store
    with _store_lock:
        _store = None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def route_tier(method: str, path: str) -> str:
    if path in {"/health", "/health/wake"}:
        return "exempt"
    if (method.upper(), path) in EXPENSIVE_ROUTES:
        return "expensive"
    return "general"


def rules_for_tier(tier: str, settings: Settings) -> list[tuple[str, RateLimitRule]]:
    ip_placeholder = "{ip}"
    if tier == "exempt":
        return []
    if tier == "expensive":
        return [
            (
                f"rl:global:{ip_placeholder}",
                RateLimitRule(
                    max_requests=settings.rate_limit_global_requests,
                    window_seconds=settings.rate_limit_global_window_seconds,
                ),
            ),
            (
                f"rl:expensive:{ip_placeholder}",
                RateLimitRule(
                    max_requests=settings.rate_limit_expensive_requests,
                    window_seconds=settings.rate_limit_expensive_window_seconds,
                ),
            ),
        ]
    return [
        (
            f"rl:global:{ip_placeholder}",
            RateLimitRule(
                max_requests=settings.rate_limit_global_requests,
                window_seconds=settings.rate_limit_global_window_seconds,
            ),
        ),
        (
            f"rl:general:{ip_placeholder}",
            RateLimitRule(
                max_requests=settings.rate_limit_general_requests,
                window_seconds=settings.rate_limit_general_window_seconds,
            ),
        ),
    ]


class RateLimiter:
    def __init__(self, store: RateLimitStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def check(self, client_ip: str, method: str, path: str) -> RateLimitResult | None:
        if not self._settings.rate_limit_enabled:
            return None

        tier = route_tier(method, path)
        if tier == "exempt":
            return None

        tightest: RateLimitResult | None = None
        for key_template, rule in rules_for_tier(tier, self._settings):
            key = key_template.format(ip=client_ip)
            count = self._store.increment(key, rule.window_seconds)
            remaining = max(rule.max_requests - count, 0)
            window_id = int(time.time()) // rule.window_seconds
            reset_at = (window_id + 1) * rule.window_seconds
            result = RateLimitResult(
                allowed=count <= rule.max_requests,
                limit=rule.max_requests,
                remaining=remaining,
                reset_at=reset_at,
            )
            if not result.allowed:
                return result
            if tightest is None or result.remaining < tightest.remaining:
                tightest = result

        return tightest
