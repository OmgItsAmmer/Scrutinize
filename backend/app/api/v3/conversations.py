import asyncio
import json
from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_cloudinary_storage,
    get_current_user,
    get_db_session,
    get_pipeline_orchestrator,
    get_v2_llm_client,
    get_web_search_service,
    get_v4_burr_orchestrator,
)
from app.models.conversation import ChatConversation, ChatMessage, MessageStatus, RetrievalPolicy
from app.models.file import FileStatus
from app.models.processing_job import JobStatus
from app.models.user import User
from app.schemas.upload import UploadResponse
from app.schemas.v2.search import SearchV2Response
from app.schemas.v2.search import ChatMessage as PipelineMessage
from app.schemas.v2.search import ConversationState
from app.schemas.v3.conversation import (
    ConversationCreate,
    ConversationList,
    ConversationPatch,
    ConversationRead,
    MessageCreate,
    MessageList,
    MessageRead,
    ConversationSourceList,
    ConversationSourceRead,
)
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.conversation_service import ConversationService
from app.services.fly_scaler import trigger_worker_wakeup
from app.services.job_orchestrator import JobOrchestrator
from app.services.project_service import ProjectService
from app.services.upload_utils import (
    ALL_ALLOWED_EXTENSIONS,
    cloudinary_resource_type,
    detect_modality,
    ingestion_stage,
    validate_content_type,
)
from app.services.v2.llm_clients import BaseLlmClient
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.v4.burr_orchestrator import BurrOrchestrator
from app.services.v4.run_budget import BudgetExceededError
from app.services.v4.evidence_assessor import InsufficientEvidenceError
from app.services.web_search import WebSearchService
from app.workers.tasks import process_audio, process_text, process_video

router = APIRouter(prefix="/conversations", tags=["v3-conversations"])

PDF_TOOL_NAME = "generate_pdf"
PDF_TOOL_DEFAULT_QUERY = (
    "Generate a PDF document summarizing the conversation context and the most relevant "
    "information available from project sources and the web."
)
FLOWCHART_TOOL_NAME = "generate_flowchart"
FLOWCHART_TOOL_DEFAULT_QUERY = (
    "Generate a Mermaid flowchart diagram visualizing the processes, architectures, or workflows "
    "from the project sources and conversation context."
)
TOOL_TITLE_HINTS = {
    PDF_TOOL_NAME: "Draft Document",
    FLOWCHART_TOOL_NAME: "Build Flowchart",
}

TASK_BY_MODALITY = {
    "text": process_text,
    "audio": process_audio,
    "video": process_video,
}


def _conversation_read(item: ChatConversation) -> ConversationRead:
    return ConversationRead.model_validate(item, from_attributes=True)


def _message_read(item: ChatMessage) -> MessageRead:
    return MessageRead.model_validate(item, from_attributes=True)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _resolve_turn(body: MessageCreate) -> tuple[str, str | None, str | None]:
    requested_tool = body.requested_tool.strip() if body.requested_tool else None
    content = body.content.strip()
    if requested_tool == PDF_TOOL_NAME and not content:
        content = PDF_TOOL_DEFAULT_QUERY
    elif requested_tool == FLOWCHART_TOOL_NAME and not content:
        content = FLOWCHART_TOOL_DEFAULT_QUERY
    return content, requested_tool, TOOL_TITLE_HINTS.get(requested_tool or "")


def _parse_v2_sse(block: str) -> dict | None:
    for line in block.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return None


@router.post("", response_model=ConversationRead, status_code=201)
def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConversationRead:
    item = ConversationService(session).create(
        user, scope=body.scope, project_id=body.project_id, title=body.title
    )
    return _conversation_read(item)


@router.get("", response_model=ConversationList)
def list_conversations(
    scope: str | None = Query(default=None, pattern="^(general|project)$"),
    project_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConversationList:
    items = ConversationService(session).list(
        user, scope=scope, project_id=project_id, limit=limit
    )
    return ConversationList(
        conversations=[_conversation_read(item) for item in items], total=len(items)
    )


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConversationRead:
    return _conversation_read(ConversationService(session).get(user, conversation_id))


@router.patch("/{conversation_id}", response_model=ConversationRead)
def patch_conversation(
    conversation_id: UUID,
    body: ConversationPatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConversationRead:
    return _conversation_read(
        ConversationService(session).patch(
            user, conversation_id, title=body.title, archived=body.archived
        )
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    ConversationService(session).delete(user, conversation_id)


@router.get("/{conversation_id}/messages", response_model=MessageList)
def list_messages(
    conversation_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> MessageList:
    items = ConversationService(session).messages(user, conversation_id, limit=limit)
    return MessageList(messages=[_message_read(item) for item in items], total=len(items))


@router.get("/{conversation_id}/sources", response_model=ConversationSourceList)
def list_conversation_sources(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConversationSourceList:
    files = ConversationService(session).list_sources(user, conversation_id)
    return ConversationSourceList(
        sources=[
            ConversationSourceRead(
                file_id=item.id,
                filename=item.filename,
                modality=item.modality.value,
                status=item.status.value,
                uploaded_at=item.uploaded_at,
            )
            for item in files
        ],
        total=len(files),
    )


@router.post("/{conversation_id}/sources", response_model=UploadResponse, status_code=202)
async def upload_conversation_source(
    conversation_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage: CloudinaryStorage = Depends(get_cloudinary_storage),
    settings: Settings = Depends(get_app_settings),
) -> UploadResponse:
    service = ConversationService(session)
    conversation = service.get(user, conversation_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    safe_filename = Path(file.filename).name
    modality = detect_modality(safe_filename)
    if modality is None:
        allowed = ", ".join(sorted(ALL_ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=415, detail=f"Unsupported file type. Allowed: {allowed}")

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

    upload_result = storage.upload_bytes(
        data,
        filename=safe_filename,
        modality=modality.value,
        resource_type=cloudinary_resource_type(modality),
    )

    orchestrator = JobOrchestrator(session)
    file_record = orchestrator.create_file(
        filename=safe_filename,
        modality=modality,
        storage_path=upload_result.secure_url,
        size_bytes=len(data),
        project_id=conversation.project_id,
        conversation_id=conversation.id,
    )
    job = orchestrator.create_job(file_id=file_record.id, stage=ingestion_stage(modality))
    orchestrator.mark_file_status(file_record.id, FileStatus.PROCESSING)

    task = TASK_BY_MODALITY[modality.value]
    trigger_worker_wakeup()
    task.delay(str(job.id))

    return UploadResponse(
        file_id=file_record.id,
        job_id=job.id,
        filename=file_record.filename,
        modality=file_record.modality,
        status=JobStatus.PENDING,
    )


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    body: MessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    llm: BaseLlmClient = Depends(get_v2_llm_client),
    web: WebSearchService = Depends(get_web_search_service),
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
    burr_orchestrator: BurrOrchestrator = Depends(get_v4_burr_orchestrator),
) -> StreamingResponse:
    service = ConversationService(session)
    turn_content, requested_tool, title_hint = _resolve_turn(body)
    user_display_content = (
        "" if requested_tool and not body.content.strip() else turn_content
    )
    conversation, user_message, assistant = service.begin_turn(
        user,
        conversation_id,
        user_display_content,
        body.client_message_id,
        title_hint=title_hint,
    )
    has_corpus = service.has_indexed_sources(
        conversation_id,
        conversation.project_id,
    )

    project_ctx = None
    if conversation.project_id is not None:
        project = ProjectService(session).get_by_id(conversation.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project_ctx = ProjectService(session).resolve_context(project, settings)

    prior = service.messages(user, conversation_id, limit=20)
    history = [
        PipelineMessage(role=item.role, content=item.content, timestamp=item.created_at)
        for item in prior
        if item.id not in {user_message.id, assistant.id}
        and item.status == "completed"
        and item.role in {"user", "assistant"}
    ]

    # Pre-serialize and extract primitives to avoid lazy-loading DetachedInstanceError
    user_message_data = _message_read(user_message).model_dump()
    assistant_id = assistant.id
    retrieval_policy = conversation.retrieval_policy
    project_id = conversation.project_id

    async def generate():
        yield _sse("message.accepted", {"user_message": user_message_data})
        answer = ""
        citations: list[dict] = []
        try:
            use_pipeline = (
                retrieval_policy != RetrievalPolicy.WEB_ONLY
                or has_corpus
            )
            if not use_pipeline:
                yield _sse("status", {"phase": "web_search", "step": "web_search", "label": "Searching the web"})
                
                if await request.is_disconnected():
                    await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                    return

                results = await web.search(turn_content, limit=5)
                citations = [
                    {
                        "title": item.get("title", "Web result"),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                    }
                    for item in results
                ]
                
                if await request.is_disconnected():
                    await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                    return

                yield _sse(
                    "status",
                    {
                        "phase": "web_search",
                        "step": "web_search_end",
                        "label": f"Found {len(citations)} web results",
                        "sources_count": len(citations),
                        "sources": citations,
                    },
                )
                web_context = "\n\n".join(
                    f"[{index + 1}] {item['title']}\n{item['url']}\n{item['snippet']}"
                    for index, item in enumerate(citations)
                ) or "No web results were available. Be transparent about this."
                history_text = "\n".join(f"{m.role}: {m.content}" for m in history[-10:])
                prompt = (
                    f"Conversation:\n{history_text}\n\nUser: {turn_content}"
                    f"\n\nWeb results:\n{web_context}"
                )
                system = (
                    "You are Scrutinize general chat. Answer conversationally using only "
                    "the provided web results for factual claims. Cite sources as markdown "
                    "links. Never claim access to project files or project retrieval."
                )
                
                if await request.is_disconnected():
                    await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                    return

                yield _sse("status", {"phase": "synthesis", "step": "synthesis", "label": "Generating reply"})
                
                generator = llm.generate_stream(settings.local_llm_gate_model, system, prompt)
                
                def get_next_chunk(gen):
                    try:
                        return next(gen)
                    except StopIteration:
                        return None
                        
                while True:
                    if await request.is_disconnected():
                        await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                        return
                    chunk = await asyncio.to_thread(get_next_chunk, generator)
                    if chunk is None:
                        break
                    answer += chunk
                    yield _sse("delta", {"assistant_message_id": assistant_id, "text": chunk})
            else:
                web_search_mode = body.web_search_mode
                retrieval_citations: list[dict] = []
                
                generator = burr_orchestrator.search_stream(
                    turn_content,
                    project_ctx=project_ctx,
                    conversation=ConversationState(messages=history),
                    web_search_mode=web_search_mode,
                    client_requested_tool=requested_tool,
                    conversation_id=conversation_id,
                    has_corpus=has_corpus,
                    use_cloud_llm=body.use_cloud_llm or False,
                )
                
                def get_next_block(gen):
                    try:
                        return next(gen)
                    except StopIteration:
                        return None
                        
                while True:
                    if await request.is_disconnected():
                        await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                        return
                    block = await asyncio.to_thread(get_next_block, generator)
                    if block is None:
                        break
                    
                    event = _parse_v2_sse(block)
                    if not event:
                        continue
                    event_name = event.get("event")
                    data = event.get("data") or {}
                    if event_name == "status":
                        if data.get("step") == "retrieval_end":
                            retrieval_citations = list(data.get("sources") or [])
                        yield _sse("status", data)
                    elif event_name == "chunk":
                        chunk = data.get("text", "")
                        answer += chunk
                        yield _sse("delta", {"assistant_message_id": assistant_id, "text": chunk})
                    elif event_name == "result":
                        try:
                            result = SearchV2Response.model_validate(data)
                            answer = result.answer
                            citations = [source.model_dump(mode="json") for source in result.sources]
                        except Exception as exc:
                            import logging
                            logging.getLogger(__name__).warning(
                                "Pipeline result validation failed; falling back to streamed answer: %s",
                                exc,
                            )
                    elif event_name == "error":
                        raise RuntimeError(data.get("message", "Project search failed"))
                        
                if result is None:
                    if not answer.strip():
                        raise RuntimeError("Project search ended before a final result was received.")
                    if not citations and retrieval_citations:
                        citations = retrieval_citations

            if await request.is_disconnected():
                await asyncio.to_thread(db_fail_message, assistant_id, "cancelled")
                return

            assistant_data, conversation_data = await asyncio.to_thread(
                db_complete_message, assistant_id, conversation_id, answer, citations, settings, llm
            )
            yield _sse(
                "message.completed",
                {
                    "assistant_message": assistant_data,
                    "conversation": conversation_data,
                },
            )
        except InsufficientEvidenceError as exc:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            abstention_message = str(exc) or "I could not find sufficient information in the provided sources."
            await asyncio.to_thread(db_abstain_message, assistant_id, abstention_message)
            yield _sse(
                "error",
                {"code": "StopReason.insufficient_evidence", "retryable": False, "message": abstention_message},
            )
        except BudgetExceededError as exc:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            await asyncio.to_thread(db_fail_message, assistant_id, "budget_exceeded")
            yield _sse(
                "error",
                {"code": "StopReason.budget_exceeded", "retryable": False, "message": str(exc)},
            )
        except Exception as exc:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            await asyncio.to_thread(db_fail_message, assistant_id, "execution_failed")
            yield _sse(
                "error",
                {"code": "execution_failed", "retryable": True, "message": str(exc)},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


import threading
_db_lock = threading.Lock()


def db_complete_message(
    assistant_id: UUID,
    conversation_id: UUID,
    answer: str,
    citations: list[dict],
    settings_obj: Settings,
    llm_obj: BaseLlmClient,
) -> tuple[dict | None, dict | None]:
    from app.core.database import get_engine
    from sqlmodel import Session as DBSession
    from app.services.conversation_service import ConversationService
    from app.models.conversation import ChatMessage, ChatConversation
    from sqlmodel import select

    with _db_lock:
        with DBSession(get_engine()) as db:
            svc = ConversationService(db)
            ast = db.get(ChatMessage, assistant_id)
            conv = db.get(ChatConversation, conversation_id)
            if ast:
                svc.complete(ast, answer, citations)
                db.commit()
            if conv:
                if conv.project_id:
                    try:
                        from sqlalchemy import func
                        completed_count = db.scalar(
                            select(func.count(ChatMessage.id))
                            .join(ChatConversation, ChatMessage.conversation_id == ChatConversation.id)
                            .where(ChatConversation.project_id == conv.project_id)
                            .where(ChatMessage.role == "assistant")
                            .where(ChatMessage.status == "completed")
                        )
                        if completed_count and completed_count > 0 and completed_count % 5 == 0:
                            from app.services.v2.prompt_generator import recreate_project_svg
                            recreate_project_svg(
                                project_id=conv.project_id,
                                session=db,
                                settings=settings_obj,
                                llm=llm_obj,
                            )
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).error("Failed to update project SVG on 5th message: %s", exc)

            ast_data = _message_read(ast).model_dump() if ast else None
            conv_data = _conversation_read(conv).model_dump() if conv else None
            return ast_data, conv_data


def db_fail_message(assistant_id: UUID, status: str) -> None:
    from app.core.database import get_engine
    from sqlmodel import Session as DBSession
    from app.services.conversation_service import ConversationService
    from app.models.conversation import ChatMessage
    with _db_lock:
        with DBSession(get_engine()) as db:
            svc = ConversationService(db)
            ast = db.get(ChatMessage, assistant_id)
            if ast:
                svc.fail(ast, status)
                db.commit()


def db_abstain_message(assistant_id: UUID, message: str) -> None:
    from app.core.database import get_engine
    from sqlmodel import Session as DBSession
    from app.services.conversation_service import ConversationService
    from app.models.conversation import ChatMessage
    with _db_lock:
        with DBSession(get_engine()) as db:
            svc = ConversationService(db)
            ast = db.get(ChatMessage, assistant_id)
            if ast:
                svc.complete(ast, message, [])
                db.commit()
