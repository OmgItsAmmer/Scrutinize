from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.v2.project import ProjectContext
from app.services.agents.router_agent import RouterAgent
from app.services.agents.synthesis_agent import SynthesisAgent
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.project_service import ProjectService
from app.services.search_service import SearchService
from app.services.v2.conversation_memory import ConversationMemory
from app.services.v2.decision_agent import DecisionAgent
from app.services.v2.generic_agent import GenericAgent
from app.services.v2.llm_clients import BaseLlmClient, LocalLlmClient, CloudLlmClient
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.v2.query_rewriter import QueryRewriter
from app.services.v2.rag_gate import RagGate
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent
from app.services.v2.rrf_retriever import RrfRetriever
from app.services.vector_store import VectorStore


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_app_settings() -> Settings:
    return get_settings()


def get_job_orchestrator(session: Session = Depends(get_db_session)) -> JobOrchestrator:
    return JobOrchestrator(session)


def get_cloudinary_storage(settings: Settings = Depends(get_app_settings)) -> CloudinaryStorage:
    return CloudinaryStorage(settings)


def get_embedding_service(settings: Settings = Depends(get_app_settings)) -> EmbeddingService:
    return EmbeddingService(settings)


def get_vector_store(settings: Settings = Depends(get_app_settings)) -> VectorStore:
    return VectorStore(settings)


def get_router_agent(settings: Settings = Depends(get_app_settings)) -> RouterAgent:
    return RouterAgent(settings)


def get_synthesis_agent(settings: Settings = Depends(get_app_settings)) -> SynthesisAgent:
    return SynthesisAgent(settings)


def get_v2_llm_client(settings: Settings = Depends(get_app_settings)) -> BaseLlmClient:
    if settings.use_cloud_llm:
        return CloudLlmClient(settings)
    return LocalLlmClient(settings)


def get_query_rewriter(
    llm_client: BaseLlmClient = Depends(get_v2_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> QueryRewriter:
    return QueryRewriter(llm_client, settings)


def get_rag_gate(
    llm_client: BaseLlmClient = Depends(get_v2_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RagGate:
    return RagGate(llm_client, settings)


def get_generic_agent(
    llm_client: BaseLlmClient = Depends(get_v2_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> GenericAgent:
    return GenericAgent(llm_client, settings)


def get_rrf_retriever(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_app_settings),
) -> RrfRetriever:
    return RrfRetriever(embedding_service, vector_store, settings)


def get_rag_synthesis_agent(
    llm_client: BaseLlmClient = Depends(get_v2_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RagSynthesisAgent:
    return RagSynthesisAgent(llm_client, settings)


def get_decision_agent(
    llm_client: BaseLlmClient = Depends(get_v2_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> DecisionAgent:
    return DecisionAgent(llm_client, settings)


def get_conversation_memory(
    settings: Settings = Depends(get_app_settings),
) -> ConversationMemory:
    return ConversationMemory(settings)


def get_pipeline_orchestrator(
    rewriter: QueryRewriter = Depends(get_query_rewriter),
    gate: RagGate = Depends(get_rag_gate),
    generic_agent: GenericAgent = Depends(get_generic_agent),
    rrf_retriever: RrfRetriever = Depends(get_rrf_retriever),
    rag_synthesis: RagSynthesisAgent = Depends(get_rag_synthesis_agent),
    decision_agent: DecisionAgent = Depends(get_decision_agent),
    conversation_memory: ConversationMemory = Depends(get_conversation_memory),
    settings: Settings = Depends(get_app_settings),
    session: Session = Depends(get_db_session),
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        rewriter,
        gate,
        generic_agent,
        rrf_retriever,
        rag_synthesis,
        decision_agent,
        conversation_memory,
        settings,
        session,
    )


# ---------------------------------------------------------------------------
# Multi-tenant project auth dependencies
# ---------------------------------------------------------------------------


def get_project_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectService:
    return ProjectService(session)


def get_project_from_admin_key(
    x_project_key: str = Header(
        ...,
        alias="X-Project-Key",
        description="Private admin key (scrutinize_sk_...) issued on project registration.",
    ),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectContext:
    """Validate a private admin API key and resolve a ProjectContext.

    Used on upload/management endpoints. Raises HTTP 401 for invalid keys.
    """
    svc = ProjectService(session)
    project = svc.get_by_admin_key(x_project_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Project-Key (admin key).")
    return svc.resolve_context(project, settings)


def get_project_from_client_key(
    x_project_key: str = Header(
        ...,
        alias="X-Project-Key",
        description="Public client key (scrutinize_pk_...) issued on project registration.",
    ),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectContext:
    """Validate a public client API key and resolve a ProjectContext.

    Used on search/chat endpoints. Raises HTTP 401 for invalid keys.
    """
    svc = ProjectService(session)
    project = svc.get_by_client_key(x_project_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Project-Key (client key).")
    return svc.resolve_context(project, settings)


def get_search_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
    router_agent: RouterAgent = Depends(get_router_agent),
    synthesis_agent: SynthesisAgent = Depends(get_synthesis_agent),
    settings: Settings = Depends(get_app_settings),
) -> SearchService:
    return SearchService(
        embedding_service,
        vector_store,
        router_agent,
        synthesis_agent,
        settings,
    )
