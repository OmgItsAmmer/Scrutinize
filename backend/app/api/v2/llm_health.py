from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.deps import get_app_settings
from app.schemas.v2.llm_health import LlmHealthResponse
from app.services.v2.llm_clients.local import LocalLlmClient, LocalLlmError

router = APIRouter()


@router.get("/llm-health", response_model=LlmHealthResponse, tags=["v2"])
def llm_health(settings: Settings = Depends(get_app_settings)) -> LlmHealthResponse:
    """Ping the configured gate model via the local LLM endpoint."""
    if not settings.local_llm_configured:
        return LlmHealthResponse(
            status="error",
            detail="LOCAL_LLM_BASE_URL is not configured",
        )

    model = settings.local_llm_gate_model
    client = LocalLlmClient(settings)
    try:
        response_obj = client.generate(
            model,
            system="Reply with exactly: ok",
            user="ping",
        )
        reply = response_obj.content
    except LocalLlmError as exc:
        return LlmHealthResponse(status="error", model=model, detail=str(exc))

    sample = reply if len(reply) <= 120 else f"{reply[:117]}..."
    return LlmHealthResponse(status="ok", model=model, sample_response=sample)
