import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.config import Settings
from app.core.deps import (
    get_app_settings,
    get_current_user,
    get_db_session,
    get_pipeline_orchestrator,
    get_v2_llm_client,
    get_web_search_service,
)
from app.models.conversation import ChatConversation, ChatMessage, RetrievalPolicy
from app.models.user import User
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
)
from app.services.conversation_service import ConversationService
from app.services.project_service import ProjectService
from app.services.v2.llm_clients import BaseLlmClient
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.web_search import WebSearchService

router = APIRouter(prefix="/conversations", tags=["v3-conversations"])


def _conversation_read(item: ChatConversation) -> ConversationRead:
    return ConversationRead.model_validate(item, from_attributes=True)


def _message_read(item: ChatMessage) -> MessageRead:
    return MessageRead.model_validate(item, from_attributes=True)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


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
    ConversationService(session).patch(user, conversation_id, title=None, archived=True)


@router.get("/{conversation_id}/messages", response_model=MessageList)
def list_messages(
    conversation_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> MessageList:
    items = ConversationService(session).messages(user, conversation_id, limit=limit)
    return MessageList(messages=[_message_read(item) for item in items], total=len(items))


@router.post("/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: UUID,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    llm: BaseLlmClient = Depends(get_v2_llm_client),
    web: WebSearchService = Depends(get_web_search_service),
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
) -> StreamingResponse:
    service = ConversationService(session)
    conversation, user_message, assistant = service.begin_turn(
        user, conversation_id, body.content, body.client_message_id
    )

    def generate():
        yield _sse("message.accepted", {"user_message": _message_read(user_message).model_dump()})
        prior = service.messages(user, conversation_id, limit=20)
        history = [
            PipelineMessage(role=item.role, content=item.content, timestamp=item.created_at)
            for item in prior
            if item.id not in {user_message.id, assistant.id}
            and item.status == "completed"
            and item.role in {"user", "assistant"}
        ]
        answer = ""
        citations: list[dict] = []
        try:
            if conversation.retrieval_policy == RetrievalPolicy.WEB_ONLY:
                yield _sse("status", {"phase": "web_search", "step": "web_search", "label": "Searching the web"})
                results = asyncio.run(web.search(body.content, limit=5))
                citations = [
                    {
                        "title": item.get("title", "Web result"),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                    }
                    for item in results
                ]
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
                    f"Conversation:\n{history_text}\n\nUser: {body.content}"
                    f"\n\nWeb results:\n{web_context}"
                )
                system = (
                    "You are Scrutinize general chat. Answer conversationally using only "
                    "the provided web results for factual claims. Cite sources as markdown "
                    "links. Never claim access to project files or project retrieval."
                )
                yield _sse("status", {"phase": "synthesis", "step": "synthesis", "label": "Generating reply"})
                for chunk in llm.generate_stream(settings.local_llm_gate_model, system, prompt):
                    answer += chunk
                    yield _sse("delta", {"assistant_message_id": assistant.id, "text": chunk})
            else:
                if conversation.project_id is None:
                    raise RuntimeError("Project conversation is missing project_id")
                project = ProjectService(session).get_by_id(conversation.project_id)
                if project is None:
                    raise RuntimeError("Project not found")
                project_ctx = ProjectService(session).resolve_context(project, settings)
                result: SearchV2Response | None = None
                for block in orchestrator.search_stream(
                    body.content,
                    project_ctx=project_ctx,
                    conversation=ConversationState(messages=history),
                    web_search_mode="auto",
                ):
                    event = _parse_v2_sse(block)
                    if not event:
                        continue
                    event_name = event.get("event")
                    data = event.get("data") or {}
                    if event_name == "status":
                        yield _sse("status", data)
                    elif event_name == "chunk":
                        chunk = data.get("text", "")
                        answer += chunk
                        yield _sse("delta", {"assistant_message_id": assistant.id, "text": chunk})
                    elif event_name == "result":
                        result = SearchV2Response.model_validate(data)
                        answer = result.answer
                        citations = [source.model_dump(mode="json") for source in result.sources]
                    elif event_name == "error":
                        raise RuntimeError(data.get("message", "Project search failed"))
                if result is None:
                    raise RuntimeError("Project search ended before a final result was received.")
            service.complete(assistant, answer, citations)
            session.refresh(assistant)
            session.refresh(conversation)
            yield _sse(
                "message.completed",
                {
                    "assistant_message": _message_read(assistant).model_dump(),
                    "conversation": _conversation_read(conversation).model_dump(),
                },
            )
        except Exception as exc:
            service.fail(assistant, "execution_failed")
            yield _sse(
                "error",
                {"code": "execution_failed", "retryable": True, "message": str(exc)},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
