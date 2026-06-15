from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("scrutinize", broker=settings.broker_url, backend=settings.result_backend)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

celery_app.autodiscover_tasks(["app.workers"])

from app.workers import tasks as _tasks  # noqa: F401, E402
