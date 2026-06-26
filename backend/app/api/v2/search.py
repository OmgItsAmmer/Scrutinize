from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_pipeline_orchestrator
from app.schemas.v2.search import SearchV2Request, SearchV2Response
from app.services.v2.llm_clients.local import LocalLlmError
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post("/search", response_model=SearchV2Response, tags=["v2"])
def search_v2(
    body: SearchV2Request,
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
) -> SearchV2Response:
    try:
        return orchestrator.search(
            body.query,
            modality_filter=body.modality_filter,
            conversation=body.conversation,
        )
    except LocalLlmError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local LLM is unavailable: {exc}",
        ) from exc
