import logging
import os
import signal
import threading
import time
from celery import Celery
from celery.signals import worker_ready, task_prerun, task_postrun

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

# Idle shutdown monitor variables
_running_tasks = 0
_last_activity = time.time()
_lock = threading.Lock()

@task_prerun.connect
def _on_task_prerun(*args: object, **kwargs: object) -> None:
    global _running_tasks, _last_activity
    with _lock:
        _running_tasks += 1
        _last_activity = time.time()

@task_postrun.connect
def _on_task_postrun(*args: object, **kwargs: object) -> None:
    global _running_tasks, _last_activity
    with _lock:
        _running_tasks = max(0, _running_tasks - 1)
        _last_activity = time.time()


def _monitor_idle(timeout_seconds: int) -> None:
    global _running_tasks, _last_activity
    logger.info("Starting worker idle monitor. Timeout: %ds", timeout_seconds)
    while True:
        time.sleep(10)
        with _lock:
            if _running_tasks == 0:
                idle_time = time.time() - _last_activity
                if idle_time >= timeout_seconds:
                    logger.warning("Worker has been idle for %.1fs. Shutting down worker process...", idle_time)
                    os.kill(os.getpid(), signal.SIGTERM)
                    break


@worker_ready.connect
def _log_worker_config(**_: object) -> None:
    cfg = reload_settings()
    logger.warning(
        "Celery worker ready — QDRANT_URL=%s REDIS_URL=%s (restart worker after .env changes)",
        cfg.qdrant_url,
        cfg.redis_url,
    )
    if cfg.resolved_worker_idle_timeout_seconds > 0 and not cfg.task_always_eager:
        t = threading.Thread(
            target=_monitor_idle,
            args=(cfg.resolved_worker_idle_timeout_seconds,),
            name="WorkerIdleMonitor",
            daemon=True,
        )
        t.start()


celery_app.autodiscover_tasks(["app.workers"])

from app.workers import tasks as _tasks  # noqa: F401, E402