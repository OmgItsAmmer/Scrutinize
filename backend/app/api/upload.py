from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import Settings
from app.core.deps import get_app_settings, get_cloudinary_storage, get_job_orchestrator
from app.models.file import FileStatus
from app.models.processing_job import JobStatus
from app.schemas.upload import UploadResponse
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.job_orchestrator import JobOrchestrator
from app.services.upload_utils import (
    ALL_ALLOWED_EXTENSIONS,
    cloudinary_resource_type,
    detect_modality,
    ingestion_stage,
    validate_content_type,
)
from app.workers.tasks import process_audio, process_text, process_video

router = APIRouter()

TASK_BY_MODALITY = {
    "text": process_text,
    "audio": process_audio,
    "video": process_video,
}


@router.post("/upload", response_model=UploadResponse, tags=["upload"])
async def upload_file(
    file: UploadFile = File(...),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
    storage: CloudinaryStorage = Depends(get_cloudinary_storage),
    settings: Settings = Depends(get_app_settings),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    safe_filename = Path(file.filename).name
    if safe_filename != file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    modality = detect_modality(safe_filename)
    if modality is None:
        allowed = ", ".join(sorted(ALL_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed extensions: {allowed}",
        )

    if not validate_content_type(modality, file.content_type):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type for {modality.value}: {file.content_type}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    if modality.value == "text" and not safe_filename.lower().endswith(".pdf"):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Text files must be UTF-8 encoded",
            ) from exc

    upload_result = storage.upload_bytes(
        data,
        filename=safe_filename,
        modality=modality.value,
        resource_type=cloudinary_resource_type(modality),
    )

    file_record = orchestrator.create_file(
        filename=safe_filename,
        modality=modality,
        storage_path=upload_result.secure_url,
        size_bytes=len(data),
    )
    job = orchestrator.create_job(file_id=file_record.id, stage=ingestion_stage(modality))
    orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

    task = TASK_BY_MODALITY[modality.value]
    task.delay(str(job.id))

    return UploadResponse(
        file_id=file_record.id,
        job_id=job.id,
        filename=file_record.filename,
        modality=file_record.modality,
        status=JobStatus.PENDING,
    )
