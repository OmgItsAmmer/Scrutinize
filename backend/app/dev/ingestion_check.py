"""Shared helpers for manual ingestion check scripts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import get_engine, init_db
from app.models.file import FileModality, FileStatus
from app.services.audio_processor import AudioProcessor
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.text_processor import TextProcessor
from app.services.transcription_service import TranscriptionService
from app.services.upload_utils import cloudinary_resource_type, detect_modality, ingestion_stage
from app.services.vector_store import VectorStore
from app.services.video_processor import VideoProcessor
from app.services.vision_service import VisionService


def parse_path_arg(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("file", type=Path, help="Local file to ingest")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Use file:// path only (creates DB rows with local path; no Cloudinary upload)",
    )
    return parser.parse_args()


def ensure_modality(path: Path, expected: FileModality) -> None:
    modality = detect_modality(path.name)
    if modality != expected:
        print(
            f"Expected a {expected.value} file, got {modality.value if modality else 'unknown'}: {path}",
            file=sys.stderr,
        )
        sys.exit(1)


def run_ingestion(path: Path, *, expected: FileModality, skip_upload: bool) -> int:
    settings = get_settings()
    if not settings.database_url.strip():
        print("DATABASE_URL is required.", file=sys.stderr)
        sys.exit(1)

    init_db()
    data = path.read_bytes()
    if not data:
        print("File is empty.", file=sys.stderr)
        sys.exit(1)

    with Session(get_engine()) as session:
        orchestrator = JobOrchestrator(session)

        if skip_upload:
            storage_path = path.resolve().as_uri()
        else:
            storage = CloudinaryStorage(settings)
            upload = storage.upload_bytes(
                data,
                filename=path.name,
                modality=expected.value,
                resource_type=cloudinary_resource_type(expected),
            )
            storage_path = upload.secure_url

        file_record = orchestrator.create_file(
            filename=path.name,
            modality=expected,
            storage_path=storage_path,
            size_bytes=len(data),
        )
        job = orchestrator.create_job(file_id=file_record.id, stage=ingestion_stage(expected))
        orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

        embedding_service = EmbeddingService(settings)
        vector_store = VectorStore(settings)
        transcription_service = TranscriptionService(settings)
        vision_service = VisionService(settings)

        if expected == FileModality.TEXT:
            processor = TextProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                settings,
            )
        elif expected == FileModality.AUDIO:
            processor = AudioProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                transcription_service,
                settings,
            )
        else:
            processor = VideoProcessor(
                orchestrator,
                embedding_service,
                vector_store,
                transcription_service,
                vision_service,
                settings,
            )

        segment_count = processor.process(job.id)
        points = vector_store.count_points()
        print(f"file_id: {file_record.id}")
        print(f"job_id: {job.id}")
        print(f"segments_indexed: {segment_count}")
        print(f"qdrant_points_total: {points}")
        return segment_count
