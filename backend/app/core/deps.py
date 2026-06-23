from collections.abc import Generator

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.services.agents.router_agent import RouterAgent
from app.services.agents.synthesis_agent import SynthesisAgent
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.search_service import SearchService
from app.services.v2.conversation_memory import ConversationMemory
from app.services.v2.decision_agent import DecisionAgent
from app.services.v2.generic_agent import GenericAgent
from app.services.v2.local_llm_client import LocalLlmClient
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


def get_local_llm_client(settings: Settings = Depends(get_app_settings)) -> LocalLlmClient:
    return LocalLlmClient(settings)


def get_query_rewriter(
    local_llm: LocalLlmClient = Depends(get_local_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> QueryRewriter:
    return QueryRewriter(local_llm, settings)


def get_rag_gate(
    local_llm: LocalLlmClient = Depends(get_local_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RagGate:
    return RagGate(local_llm, settings)


def get_generic_agent(
    local_llm: LocalLlmClient = Depends(get_local_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> GenericAgent:
    return GenericAgent(local_llm, settings)


def get_rrf_retriever(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_app_settings),
) -> RrfRetriever:
    return RrfRetriever(embedding_service, vector_store, settings)


def get_rag_synthesis_agent(
    local_llm: LocalLlmClient = Depends(get_local_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RagSynthesisAgent:
    return RagSynthesisAgent(local_llm, settings)


def get_decision_agent(
    local_llm: LocalLlmClient = Depends(get_local_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> DecisionAgent:
    return DecisionAgent(local_llm, settings)


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
