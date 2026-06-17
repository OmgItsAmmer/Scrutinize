import httpx
from redis import Redis
from sqlmodel import Session

from app.core.config import Settings
from app.schemas.health import DependencyCheck, HealthResponse


def check_database(session: Session) -> DependencyCheck:
    try:
        session.connection().exec_driver_sql("SELECT 1")
        return DependencyCheck(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyCheck(status="error", detail=str(exc))


def check_redis(settings: Settings) -> DependencyCheck:
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return DependencyCheck(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyCheck(status="error", detail=str(exc))


def check_qdrant(settings: Settings) -> DependencyCheck:
    try:
        headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else None
        response = httpx.get(
            f"{settings.qdrant_url.rstrip('/')}/collections",
            headers=headers,
            timeout=3.0,
        )
        response.raise_for_status()
        return DependencyCheck(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyCheck(status="error", detail=str(exc))


def build_health_response(
    settings: Settings,
    session: Session,
    *,
    version: str,
) -> HealthResponse:
    checks = {
        "database": check_database(session),
        "redis": check_redis(settings),
        "qdrant": check_qdrant(settings),
    }
    overall = "ok" if all(check.status == "ok" for check in checks.values()) else "degraded"

    return HealthResponse(
        status=overall,
        service=settings.app_name.lower(),
        version=version,
        checks=checks,
    )
