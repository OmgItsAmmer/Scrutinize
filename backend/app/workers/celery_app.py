from celery import Celery
from celery.signals import worker_ready
import logging

from app.core.config import get_settings, reload_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery("scrutinize", broker=settings.broker_url, backend=settings.result_backend)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.task_always_eager,
    task_eager_propagates=settings.task_always_eager,
)


@worker_ready.connect
def _log_worker_config(**_: object) -> None:
    cfg = reload_settings()
    logger.warning(
        "Celery worker ready — QDRANT_URL=%s REDIS_URL=%s (restart worker after .env changes)",
        cfg.qdrant_url,
        cfg.redis_url,
    )


celery_app.autodiscover_tasks(["app.workers"])

from app.workers import tasks as _tasks  # noqa: F401, E402