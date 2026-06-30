from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.models.file import File, FileModality, FileStatus
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.segment import Segment


class JobOrchestrator:
    """Coordinates processing job lifecycle in Neon Postgres."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_file(
        self,
        *,
        filename: str,
        modality: FileModality,
        storage_path: str,
        size_bytes: int | None = None,
        duration_seconds: float | None = None,
        project_id: UUID | None = None,
    ) -> File:
        file_record = File(
            filename=filename,
            modality=modality,
            storage_path=storage_path,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            status=FileStatus.UPLOADED,
            project_id=project_id,
        )
        self.session.add(file_record)
        self.session.commit()
        self.session.refresh(file_record)
        return file_record

    def create_job(self, *, file_id: UUID, stage: str) -> ProcessingJob:
        job = ProcessingJob(file_id=file_id, stage=stage, status=JobStatus.PENDING)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, job_id: UUID) -> ProcessingJob | None:
        return self.session.get(ProcessingJob, job_id)

    def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        error_message: str | None = None,
    ) -> ProcessingJob:
        job = self.session.get(ProcessingJob, job_id)
        if job is None:
            raise LookupError(f"Processing job {job_id} not found")

        job.status = status
        job.error_message = error_message
        job.updated_at = datetime.now(UTC)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_file_status(self, file_id: UUID, status: FileStatus) -> File:
        file_record = self.session.get(File, file_id)
        if file_record is None:
            raise LookupError(f"File {file_id} not found")

        file_record.status = status
        self.session.add(file_record)
        self.session.commit()
        self.session.refresh(file_record)
        return file_record

    def get_file(self, file_id: UUID) -> File | None:
        return self.session.get(File, file_id)

    def list_files(self, *, limit: int = 100, offset: int = 0, project_id: UUID | None = None) -> list[File]:
        statement = select(File)
        if project_id is not None:
            statement = statement.where(File.project_id == project_id)
        statement = statement.order_by(File.uploaded_at.desc()).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def list_jobs_for_file(self, file_id: UUID) -> list[ProcessingJob]:
        statement = select(ProcessingJob).where(ProcessingJob.file_id == file_id)
        return list(self.session.exec(statement).all())

    def create_segment(
        self,
        *,
        file_id: UUID,
        modality: FileModality,
        content: str,
        start_time: float | None = None,
        end_time: float | None = None,
        segment_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Segment:
        segment = Segment(
            id=segment_id or uuid4(),
            file_id=file_id,
            modality=modality,
            content=content,
            start_time=start_time,
            end_time=end_time,
            project_id=project_id,
        )
        self.session.add(segment)
        self.session.commit()
        self.session.refresh(segment)
        return segment

    def list_segments_for_file(self, file_id: UUID) -> list[Segment]:
        statement = select(Segment).where(Segment.file_id == file_id)
        return list(self.session.exec(statement).all())

    def delete_file(self, file_id: UUID) -> File:
        file_record = self.session.get(File, file_id)
        if file_record is None:
            raise LookupError(f"File {file_id} not found")

        for segment in self.list_segments_for_file(file_id):
            self.session.delete(segment)
        for job in self.list_jobs_for_file(file_id):
            self.session.delete(job)

        # SQLAlchemy may flush DELETE files before child rows without an explicit flush.
        self.session.flush()

        self.session.delete(file_record)
        self.session.commit()
        return file_record
