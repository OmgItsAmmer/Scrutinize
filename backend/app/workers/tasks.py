from app.workers.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Smoke task to verify Celery worker connectivity."""
    return "pong"


@celery_app.task(name="process_file", bind=True)
def process_file(self, job_id: str, stage: str) -> dict[str, str]:
    """Placeholder ingestion task — replaced by M2–M4 modality processors."""
    return {"job_id": job_id, "stage": stage, "status": "pending"}

