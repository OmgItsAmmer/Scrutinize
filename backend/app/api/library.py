from fastapi import APIRouter, Depends, Query

from app.core.deps import get_job_orchestrator
from app.schemas.library import LibraryFileItem, LibraryResponse
from app.services.job_orchestrator import JobOrchestrator

router = APIRouter()


@router.get("/library", response_model=LibraryResponse, tags=["library"])
def list_library(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
) -> LibraryResponse:
    files = orchestrator.list_files(limit=limit, offset=offset)
    items = [
        LibraryFileItem(
            id=file_record.id,
            filename=file_record.filename,
            modality=file_record.modality,
            status=file_record.status,
            segment_count=len(orchestrator.list_segments_for_file(file_record.id)),
            uploaded_at=file_record.uploaded_at,
            duration_seconds=file_record.duration_seconds,
            size_bytes=file_record.size_bytes,
        )
        for file_record in files
    ]
    return LibraryResponse(files=items, total=len(items))
