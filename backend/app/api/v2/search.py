
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_db_session,
    get_pipeline_orchestrator,
    get_project_from_client_key,
)
from app.schemas.v2.project import ProjectContext
from app.schemas.v2.search import SearchV2Request, SearchV2Response
from app.services.v2.llm_clients.local import LocalLlmError
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post("/search", response_model=SearchV2Response, tags=["v2"])
def search_v2(
    body: SearchV2Request,
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
    project_ctx: ProjectContext = Depends(get_project_from_client_key),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> SearchV2Response:
    """Run the v2 search pipeline.

    Supply an **X-Project-Key** header (public client key) to scope the search to a
    specific project's indexed documents and use per-project model overrides.
    Without the header, the search runs against the legacy un-tenanted corpus.
    """
    try:
        return orchestrator.search(
            body.query,
            project_ctx=project_ctx,
            modality_filter=body.modality_filter,
            conversation=body.conversation,
            web_search_mode=body.web_search_mode,
        )
    except LocalLlmError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local LLM is unavailable: {exc}",
        ) from exc


@router.post("/search/stream", tags=["v2"])
def search_v2_stream(
    body: SearchV2Request,
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
    project_ctx: ProjectContext = Depends(get_project_from_client_key),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> StreamingResponse:
    """Run the v2 search pipeline and stream SSE status updates & final result."""
    try:
        generator = orchestrator.search_stream(
            body.query,
            project_ctx=project_ctx,
            modality_filter=body.modality_filter,
            conversation=body.conversation,
            web_search_mode=body.web_search_mode,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except LocalLlmError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local LLM is unavailable: {exc}",
        ) from exc


