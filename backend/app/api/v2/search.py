from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_db_session,
    get_pipeline_orchestrator,
)
from app.schemas.v2.project import ProjectContext
from app.schemas.v2.search import SearchV2Request, SearchV2Response
from app.services.project_service import ProjectService
from app.services.v2.llm_clients.local import LocalLlmError
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post("/search", response_model=SearchV2Response, tags=["v2"])
def search_v2(
    body: SearchV2Request,
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
    x_project_key: Annotated[str | None, Header(alias="X-Project-Key")] = None,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> SearchV2Response:
    """Run the v2 search pipeline.

    Supply an **X-Project-Key** header (public client key) to scope the search to a
    specific project's indexed documents and use per-project model overrides.
    Without the header, the search runs against the legacy un-tenanted corpus.
    """
    project_ctx: ProjectContext | None = None
    if x_project_key:
        svc = ProjectService(session)
        project = svc.get_by_client_key(x_project_key)
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid X-Project-Key (client key).")
        project_ctx = svc.resolve_context(project, settings)

    try:
        return orchestrator.search(
            body.query,
            project_ctx=project_ctx,
            modality_filter=body.modality_filter,
            conversation=body.conversation,
        )
    except LocalLlmError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local LLM is unavailable: {exc}",
        ) from exc

