"""Read-only pipeline-trace endpoints for the developer debug sidebar.

Gated by `settings.dev_ui_enabled` (env `DEV_UI=true`) — 404s otherwise so the
surface doesn't leak in production. Access is still scoped to the requesting
user's own conversations via `ConversationService.get`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.deps import get_app_settings, get_current_user, get_db_session
from app.models.conversation import ChatMessage
from app.models.pipeline_log import PipelineRun, PipelineStep
from app.models.user import User
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/debug", tags=["v3-debug"])


def _require_dev_ui(settings: Settings) -> None:
    if not settings.dev_ui_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _step_dict(step: PipelineStep, *, include_candidates: bool = False) -> dict:
    data = {
        "id": str(step.id),
        "step_type": step.step_type,
        "attempt": step.attempt,
        "model_name": step.model_name,
        "model_input": step.model_input,
        "raw_thinking": step.raw_thinking,
        "model_output": step.model_output,
        "structured_output": step.structured_output,
        "retrieved_sources": step.retrieved_sources,
        "has_candidates": bool(step.retrieval_candidates),
        "candidate_count": len(step.retrieval_candidates) if step.retrieval_candidates else 0,
        "latency_ms": step.latency_ms,
        "status": step.status,
        "prompt_tokens": step.prompt_tokens,
        "completion_tokens": step.completion_tokens,
        "cached_tokens": step.cached_tokens,
        "cost_usd": float(step.cost_usd) if step.cost_usd is not None else None,
        "created_at": step.created_at.isoformat(),
    }
    if include_candidates:
        data["retrieval_candidates"] = step.retrieval_candidates
    return data


def _run_dict(run: PipelineRun, steps: list[PipelineStep]) -> dict:
    return {
        "id": str(run.id),
        "original_query": run.original_query,
        "modality_filter": run.modality_filter,
        "conversation_context": run.conversation_context,
        "start_time": run.start_time.isoformat(),
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "final_route": run.final_route,
        "final_answer": run.final_answer,
        "final_confidence": float(run.final_confidence) if run.final_confidence is not None else None,
        "attempts_count": run.attempts_count,
        "disclaimer_appended": run.disclaimer_appended,
        "total_cost_usd": float(run.total_cost_usd) if run.total_cost_usd is not None else None,
        "total_tokens": run.total_tokens,
        "created_at": run.created_at.isoformat(),
        "steps": [_step_dict(step) for step in steps],
    }


def _load_trace(session: Session, run_id: UUID) -> dict:
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    steps = list(
        session.exec(
            select(PipelineStep)
            .where(PipelineStep.run_id == run_id)
            .order_by(PipelineStep.created_at.asc())
        )
    )
    return _run_dict(run, steps)


@router.get("/messages/{message_id}/trace")
def get_message_trace(
    message_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    _require_dev_ui(settings)

    message = session.get(ChatMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    ConversationService(session).get(user, message.conversation_id)  # enforces ownership, 404s otherwise

    if message.pipeline_run_id is None:
        raise HTTPException(status_code=404, detail="No pipeline trace recorded for this message")

    return _load_trace(session, message.pipeline_run_id)


@router.get("/runs/{run_id}/trace")
def get_run_trace(
    run_id: UUID,
    conversation_id: UUID = Query(..., description="Conversation the run belongs to, for ownership checks"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    _require_dev_ui(settings)
    ConversationService(session).get(user, conversation_id)  # enforces ownership, 404s otherwise
    return _load_trace(session, run_id)


@router.get("/runs/{run_id}/retrieval-candidates")
def get_retrieval_candidates(
    run_id: UUID,
    conversation_id: UUID = Query(..., description="Conversation the run belongs to, for ownership checks"),
    attempt: int | None = Query(default=None, description="Retrieval attempt; defaults to the latest"),
    match: str = Query(default="all", pattern="^(all|semantic|keyword|both)$"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    _require_dev_ui(settings)
    ConversationService(session).get(user, conversation_id)  # enforces ownership, 404s otherwise

    statement = (
        select(PipelineStep)
        .where(PipelineStep.run_id == run_id, PipelineStep.step_type == "retrieval")
        .order_by(PipelineStep.attempt.desc() if attempt is None else PipelineStep.attempt.asc())
    )
    if attempt is not None:
        statement = statement.where(PipelineStep.attempt == attempt)
    step = session.exec(statement).first()
    if step is None:
        raise HTTPException(status_code=404, detail="No retrieval step found for this run")

    candidates = list(step.retrieval_candidates or [])

    def _matches(candidate: dict) -> bool:
        in_semantic = bool(candidate.get("in_semantic_list"))
        in_keyword = bool(candidate.get("in_keyword_list"))
        if match == "semantic":
            return in_semantic and not in_keyword
        if match == "keyword":
            return in_keyword and not in_semantic
        if match == "both":
            return in_semantic and in_keyword
        return True

    filtered = [c for c in candidates if _matches(c)]

    return {
        "step_id": str(step.id),
        "attempt": step.attempt,
        "total_candidates": len(candidates),
        "matched_count": len(filtered),
        "match": match,
        "candidates": filtered[:limit],
    }
