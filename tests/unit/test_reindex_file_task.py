from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.file import FileModality


@pytest.mark.unit
def test_reindex_file_deletes_stale_vectors_and_segments_after_reupsert(session):
    from app.services.job_orchestrator import JobOrchestrator
    from app.workers import tasks

    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="doc.txt",
        modality=FileModality.TEXT,
        storage_path="uploads/doc.txt",
        size_bytes=100,
    )
    stale_segment = orchestrator.create_segment(
        file_id=file_record.id, modality=FileModality.TEXT, content="stale chunk"
    )
    file_id = file_record.id
    stale_segment_id = stale_segment.id

    mock_vector_store = MagicMock()

    def fake_process(job_id):
        # Simulate TextProcessor.process() creating one fresh segment for the same file.
        orchestrator.create_segment(file_id=file_id, modality=FileModality.TEXT, content="fresh chunk")
        orchestrator.update_job_status(job_id, orchestrator.get_job(job_id).status)
        return 1

    with (
        patch("app.workers.tasks.reload_settings") as mock_reload_settings,
        patch("app.workers.tasks._build_services") as mock_build_services,
        patch("app.workers.tasks._build_context_enricher", return_value=None),
        patch("app.workers.tasks.get_engine") as mock_get_engine,
        patch("app.workers.tasks.TextProcessor") as MockTextProcessor,
    ):
        mock_reload_settings.return_value = MagicMock(qdrant_url="http://q", redis_url="redis://r")
        mock_build_services.return_value = (MagicMock(), mock_vector_store, MagicMock(), MagicMock())
        mock_get_engine.return_value = session.get_bind()
        MockTextProcessor.return_value.process.side_effect = fake_process

        # Reuse the real session's engine via a fresh Session bound to the same connection.
        with patch("app.workers.tasks.Session", return_value=session):
            session.__enter__ = lambda: session
            session.__exit__ = lambda *a: None
            result = tasks.reindex_file.run(str(file_id))

    assert result["status"] == "done"
    assert result["segments"] == 1

    mock_vector_store.delete_by_ids.assert_called_once_with([stale_segment_id])

    from sqlmodel import select
    from app.models.segment import Segment

    remaining_segments = session.exec(
        select(Segment).where(Segment.file_id == file_id)
    ).all()
    assert len(remaining_segments) == 1
    assert remaining_segments[0].content == "fresh chunk"


@pytest.mark.unit
def test_reindex_file_rejects_non_text_modality(session):
    from app.services.job_orchestrator import JobOrchestrator
    from app.workers import tasks

    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename="clip.mp4",
        modality=FileModality.VIDEO,
        storage_path="uploads/clip.mp4",
        size_bytes=100,
    )

    with (
        patch("app.workers.tasks.reload_settings", return_value=MagicMock()),
        patch("app.workers.tasks._build_services", return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock())),
        patch("app.workers.tasks._build_context_enricher", return_value=None),
        patch("app.workers.tasks.get_engine", return_value=session.get_bind()),
        patch("app.workers.tasks.Session", return_value=session),
    ):
        session.__enter__ = lambda: session
        session.__exit__ = lambda *a: None
        with pytest.raises(ValueError, match="text files"):
            tasks.reindex_file.run(str(file_record.id))


@pytest.mark.unit
def test_reindex_file_raises_for_missing_file(session):
    from app.workers import tasks

    with (
        patch("app.workers.tasks.reload_settings", return_value=MagicMock()),
        patch("app.workers.tasks._build_services", return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock())),
        patch("app.workers.tasks._build_context_enricher", return_value=None),
        patch("app.workers.tasks.get_engine", return_value=session.get_bind()),
        patch("app.workers.tasks.Session", return_value=session),
    ):
        session.__enter__ = lambda: session
        session.__exit__ = lambda *a: None
        with pytest.raises(LookupError):
            tasks.reindex_file.run(str(uuid4()))
