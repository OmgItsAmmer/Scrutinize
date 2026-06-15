from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_cloudinary_storage,
    get_job_orchestrator,
    get_vector_store,
)
from app.schemas.library import DeleteFileResponse, LibraryFileItem, LibraryResponse
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.cloudinary_utils import thumbnail_url_for
from app.services.file_deletion import FileDeletionService
from app.services.job_orchestrator import JobOrchestrator
from app.services.media_content import (
    content_type_for_filename,
    read_local_file,
    stream_remote_url,
)
from app.services.vector_store import VectorStore

router = APIRouter()


def _to_library_item(
    file_record,
    *,
    segment_count: int,
    settings: Settings,
) -> LibraryFileItem:
    thumbnail_url = None
    if settings.cloudinary_configured:
        thumbnail_url = thumbnail_url_for(
            file_record.storage_path,
            cloud_name=settings.cloudinary_cloud_name,
            modality=file_record.modality.value,
        )

    return LibraryFileItem(
        id=file_record.id,
        filename=file_record.filename,
        modality=file_record.modality,
        status=file_record.status,
        segment_count=segment_count,
        uploaded_at=file_record.uploaded_at,
        duration_seconds=file_record.duration_seconds,
        size_bytes=file_record.size_bytes,
        storage_url=file_record.storage_path,
        thumbnail_url=thumbnail_url,
    )


@router.get("/library", response_model=LibraryResponse, tags=["library"])
def list_library(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
    settings: Settings = Depends(get_app_settings),
) -> LibraryResponse:
    files = orchestrator.list_files(limit=limit, offset=offset)
    items = [
        _to_library_item(
            file_record,
            segment_count=len(orchestrator.list_segments_for_file(file_record.id)),
            settings=settings,
        )
        for file_record in files
    ]
    return LibraryResponse(files=items, total=len(items))


@router.get("/library/{file_id}/content", tags=["library"])
def stream_library_file_content(
    file_id: UUID,
    download: bool = Query(default=False),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
) -> StreamingResponse:
    file_record = orchestrator.get_file(file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    media_type = content_type_for_filename(file_record.filename)
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{file_record.filename}"',
        "Cache-Control": "private, max-age=3600",
    }
    storage = file_record.storage_path

    if storage.startswith(("http://", "https://")):
        try:
            return StreamingResponse(
                stream_remote_url(storage),
                media_type=media_type,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch file from storage: {exc}",
            ) from exc

    local_path = Path(storage)
    if not local_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on storage")

    return StreamingResponse(
        read_local_file(local_path),
        media_type=media_type,
        headers=headers,
    )


@router.delete("/library/{file_id}", response_model=DeleteFileResponse, tags=["library"])
def delete_library_file(
    file_id: UUID,
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
    storage: CloudinaryStorage = Depends(get_cloudinary_storage),
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_app_settings),
) -> DeleteFileResponse:
    service = FileDeletionService(orchestrator, storage, vector_store, settings)
    try:
        service.delete_file(file_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DeleteFileResponse(
        file_id=file_id,
        message="File deleted from Cloudinary, Qdrant, and Neon.",
    )
