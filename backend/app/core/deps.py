from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.jwt_security import InvalidTokenError, decode_access_token
from app.models.user import ProjectMember, User
from app.schemas.v2.project import ProjectContext
from app.services.cloudinary_storage import CloudinaryStorage
from app.services.embedding_service import EmbeddingService
from app.services.job_orchestrator import JobOrchestrator
from app.services.project_service import ProjectService
from app.services.v2.conversation_memory import ConversationMemory
from app.services.v2.decision_agent import DecisionAgent
from app.services.v2.generic_agent import GenericAgent
from app.services.v2.llm_clients import BaseLlmClient, CloudLlmClient, LocalLlmClient
from app.services.v2.mcp_manager import McpClientManager
from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.v2.query_rewriter import QueryRewriter
from app.services.v2.rag_gate import RagGate
from app.services.v2.retrieval_precheck import RetrievalPrecheck
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent
from app.services.v2.rrf_retriever import RrfRetriever
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.v4.rag_gate import RagGate as RagGateV4
from app.services.v4.burr_orchestrator import BurrOrchestrator
from app.services.v4.evidence_assessor import EvidenceAssessor
from app.services.v4.citation_verifier import CitationVerifier
from app.services.v4.groundedness_evaluator import GroundednessEvaluator
from app.services.v4.memory_manager import MemoryManager


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


def get_mcp_manager(settings: Settings = Depends(get_app_settings)) -> McpClientManager:
    return McpClientManager(settings)


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


def get_web_search_service(
    settings: Settings = Depends(get_app_settings),
) -> WebSearchService:
    return WebSearchService(settings)


def get_retrieval_precheck(
    retriever: RrfRetriever = Depends(get_rrf_retriever),
    settings: Settings = Depends(get_app_settings),
) -> RetrievalPrecheck:
    return RetrievalPrecheck(retriever, settings)


def get_v4_rag_gate(
    settings: Settings = Depends(get_app_settings),
) -> RagGateV4:
    return RagGateV4(settings)


def get_memory_manager(settings: Settings = Depends(get_app_settings)) -> MemoryManager:
    return MemoryManager(settings)


def get_evidence_assessor(settings: Settings = Depends(get_app_settings)) -> EvidenceAssessor:
    return EvidenceAssessor(settings)


def get_citation_verifier(settings: Settings = Depends(get_app_settings)) -> CitationVerifier:
    return CitationVerifier(settings)


def get_groundedness_evaluator(settings: Settings = Depends(get_app_settings)) -> GroundednessEvaluator:
    return GroundednessEvaluator(settings)


def get_v4_burr_orchestrator(
    rewriter: QueryRewriter = Depends(get_query_rewriter),
    gate: RagGateV4 = Depends(get_v4_rag_gate),
    generic_agent: GenericAgent = Depends(get_generic_agent),
    rrf_retriever: RrfRetriever = Depends(get_rrf_retriever),
    rag_synthesis: RagSynthesisAgent = Depends(get_rag_synthesis_agent),
    decision_agent: DecisionAgent = Depends(get_decision_agent),
    conversation_memory: ConversationMemory = Depends(get_conversation_memory),
    web_search_service: WebSearchService = Depends(get_web_search_service),
    mcp_manager: McpClientManager = Depends(get_mcp_manager),
    retrieval_precheck: RetrievalPrecheck = Depends(get_retrieval_precheck),
    settings: Settings = Depends(get_app_settings),
    session: Session = Depends(get_db_session),
    # Phase 2 dependencies
    memory_manager: MemoryManager = Depends(get_memory_manager),
    evidence_assessor: EvidenceAssessor = Depends(get_evidence_assessor),
    citation_verifier: CitationVerifier = Depends(get_citation_verifier),
    groundedness_evaluator: GroundednessEvaluator = Depends(get_groundedness_evaluator),
) -> BurrOrchestrator:
    return BurrOrchestrator(
        rewriter=rewriter,
        gate=gate,
        generic_agent=generic_agent,
        rrf_retriever=rrf_retriever,
        rag_synthesis=rag_synthesis,
        decision_agent=decision_agent,
        conversation_memory=conversation_memory,
        web_search=web_search_service,
        settings=settings,
        mcp_manager=mcp_manager,
        retrieval_precheck=retrieval_precheck,
        session=session,
        # Phase 2 services
        memory_manager=memory_manager,
        evidence_assessor=evidence_assessor,
        citation_verifier=citation_verifier,
        groundedness_evaluator=groundedness_evaluator,
    )


def get_pipeline_orchestrator(
    rewriter: QueryRewriter = Depends(get_query_rewriter),
    gate: RagGate = Depends(get_rag_gate),
    generic_agent: GenericAgent = Depends(get_generic_agent),
    rrf_retriever: RrfRetriever = Depends(get_rrf_retriever),
    rag_synthesis: RagSynthesisAgent = Depends(get_rag_synthesis_agent),
    decision_agent: DecisionAgent = Depends(get_decision_agent),
    conversation_memory: ConversationMemory = Depends(get_conversation_memory),
    web_search_service: WebSearchService = Depends(get_web_search_service),
    mcp_manager: McpClientManager = Depends(get_mcp_manager),
    retrieval_precheck: RetrievalPrecheck = Depends(get_retrieval_precheck),
    settings: Settings = Depends(get_app_settings),
    session: Session = Depends(get_db_session),
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        rewriter=rewriter,
        gate=gate,
        generic_agent=generic_agent,
        rrf_retriever=rrf_retriever,
        rag_synthesis=rag_synthesis,
        decision_agent=decision_agent,
        conversation_memory=conversation_memory,
        web_search=web_search_service,
        settings=settings,
        mcp_manager=mcp_manager,
        retrieval_precheck=retrieval_precheck,
        session=session,
    )


# ---------------------------------------------------------------------------
# Multi-tenant project auth dependencies
# ---------------------------------------------------------------------------


def get_project_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectService:
    return ProjectService(session)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        claims = decode_access_token(credentials.credentials, settings.jwt_secret_key)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc
    user = session.get(User, UUID(claims["sub"]))
    if user is None or not user.is_verified:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    return user


def get_project_from_user(
    x_project_id: UUID = Header(..., alias="X-Project-Id"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectContext:
    membership = session.get(ProjectMember, (user.id, x_project_id))
    if membership is None:
        raise HTTPException(status_code=403, detail="You are not a member of this project.")
    project = ProjectService(session).get_by_id(x_project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectService(session).resolve_context(project, settings)


def get_project_from_admin_key(
    x_project_key: str | None = Header(
        None,
        alias="X-Project-Key",
        description="Private admin key (scrutinize_sk_...) issued on project registration.",
    ),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_project_id: UUID | None = Header(None, alias="X-Project-Id"),
) -> ProjectContext:
    """Validate a private admin API key and resolve a ProjectContext.

    Used on upload/management endpoints. Raises HTTP 401 for invalid keys.
    """
    if credentials and x_project_id:
        user = get_current_user(credentials, session, settings)
        membership = session.get(ProjectMember, (user.id, x_project_id))
        if membership is None:
            raise HTTPException(status_code=403, detail="You are not a member of this project.")
        project = ProjectService(session).get_by_id(x_project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return ProjectService(session).resolve_context(project, settings)
    svc = ProjectService(session)
    project = svc.get_by_admin_key(x_project_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Project-Key (admin key).")
    return svc.resolve_context(project, settings)


def get_project_from_client_key(
    x_project_key: str | None = Header(
        None,
        alias="X-Project-Key",
        description="Public client key (scrutinize_pk_...) issued on project registration.",
    ),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_project_id: UUID | None = Header(None, alias="X-Project-Id"),
) -> ProjectContext:
    """Validate a public client API key and resolve a ProjectContext.

    Used on search/chat endpoints. Raises HTTP 401 for invalid keys.
    """
    if credentials and x_project_id:
        user = get_current_user(credentials, session, settings)
        membership = session.get(ProjectMember, (user.id, x_project_id))
        if membership is None:
            raise HTTPException(status_code=403, detail="You are not a member of this project.")
        project = ProjectService(session).get_by_id(x_project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return ProjectService(session).resolve_context(project, settings)
    svc = ProjectService(session)
    project = svc.get_by_client_key(x_project_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Project-Key (client key).")
    return svc.resolve_context(project, settings)


