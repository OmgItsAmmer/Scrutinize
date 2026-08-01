import pytest

from app.models.file import FileModality
from app.models.processing_job import JobStatus
from app.services.job_orchestrator import JobOrchestrator


@pytest.mark.unit
def test_create_and_update_job(session):
    orchestrator = JobOrchestrator(session)

    file_record = orchestrator.create_file(
        filename="notes.txt",
        modality=FileModality.TEXT,
        storage_path="uploads/notes.txt",
        size_bytes=128,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage="embedding")

    assert job.status == JobStatus.PENDING
    assert job.stage == "embedding"

    updated = orchestrator.update_job_status(job.id, JobStatus.RUNNING)
    assert updated.status == JobStatus.RUNNING

    done = orchestrator.update_job_status(job.id, JobStatus.DONE)
    assert done.status == JobStatus.DONE


@pytest.mark.unit
def test_get_job_returns_none_for_missing_id(session):
    orchestrator = JobOrchestrator(session)
    from uuid import uuid4

    assert orchestrator.get_job(uuid4()) is None


@pytest.mark.unit
def test_delete_segments_for_file_removes_rows_but_keeps_file(session):
    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="doc.pdf",
        modality=FileModality.TEXT,
        storage_path="uploads/doc.pdf",
        size_bytes=128,
    )
    orchestrator.create_segment(file_id=file_record.id, modality=FileModality.TEXT, content="chunk one")
    orchestrator.create_segment(file_id=file_record.id, modality=FileModality.TEXT, content="chunk two")

    deleted_count = orchestrator.delete_segments_for_file(file_record.id)

    assert deleted_count == 2
    assert orchestrator.list_segments_for_file(file_record.id) == []
    assert orchestrator.get_file(file_record.id) is not None
