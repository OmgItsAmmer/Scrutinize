import json
import logging
from uuid import UUID

from sqlmodel import Session

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.schemas.v2.search import ConversationState, SearchV2Response, SearchV2Route
from app.services.v2.conversation_memory import ConversationMemory
from app.services.v2.decision_agent import DecisionAgent, DecisionContext
from app.services.v2.generic_agent import GenericAgent
from app.services.v2.pipeline_logger import PipelineLogger
from app.services.v2.query_rewriter import QueryRewriter
from app.services.v2.rag_gate import GateResult, RagGate
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent
from app.services.v2.rrf_retriever import RrfRetriever

logger = logging.getLogger(__name__)

NO_INDEXED_CONTENT = "No matching indexed content found."
LOW_CONFIDENCE_DISCLAIMER = "Note: answer may vary — retrieval confidence was low."


class PipelineOrchestrator:
    """v2 query pipeline: gate → generic+decision or RAG (rewrite → retrieve → synthesize → decision)."""

    def __init__(
        self,
        rewriter: QueryRewriter,
        gate: RagGate,
        generic_agent: GenericAgent,
        rrf_retriever: RrfRetriever,
        rag_synthesis: RagSynthesisAgent,
        decision_agent: DecisionAgent,
        conversation_memory: ConversationMemory,
        settings: Settings,
        session: Session | None = None,
    ) -> None:
        self._rewriter = rewriter
        self._gate = gate
        self._generic = generic_agent
        self._rrf = rrf_retriever
        self._rag_synthesis = rag_synthesis
        self._decision = decision_agent
        self._memory = conversation_memory
        self._settings = settings
        self._db_logger = PipelineLogger(session)

    def search(
        self,
        query: str,
        *,
        modality_filter: FileModality | None = None,
        conversation: ConversationState | None = None,
    ) -> SearchV2Response:
        stripped = query.strip()
        conv_state, conversation_context = self._memory.prepare(conversation)

        run_id = self._db_logger.start_run(
            query=stripped,
            modality_filter=modality_filter,
            conversation_context=conversation_context,
        )

        gate_result = self._gate.classify(
            stripped,
            conversation_context=conversation_context,
        )
        self._db_logger.log_gate(
            run_id=run_id,
            gate_result=gate_result,
        )

        if gate_result.route == "generic":
            response = self._handle_generic_path(
                run_id=run_id,
                query=stripped,
                gate_result=gate_result,
                conv_state=conv_state,
                modality_filter=modality_filter,
                conversation_context=conversation_context,
            )
        else:
            response = self._run_rag_pipeline(
                run_id=run_id,
                stripped=stripped,
                gate_result=gate_result,
                conv_state=conv_state,
                conversation_context=conversation_context,
                modality_filter=modality_filter,
            )

        self._db_logger.end_run(
            run_id=run_id,
            final_route=response.route,
            final_answer=response.answer,
            final_confidence=response.confidence,
            attempts_count=response.attempts,
            disclaimer_appended=response.disclaimer_appended,
        )
        return response

    def _handle_generic_path(
        self,
        *,
        run_id: UUID | None,
        query: str,
        gate_result: GateResult,
        conv_state: ConversationState,
        modality_filter: FileModality | None,
        conversation_context: str,
    ) -> SearchV2Response:
        if gate_result.reply:
            answer = gate_result.reply
        else:
            generic_result = self._generic.reply(query, conversation_context=conversation_context)
            answer = generic_result.answer
            self._db_logger.log_synthesis(
                run_id=run_id,
                attempt=1,
                synthesis_result=generic_result,
            )

        decision = self._decision.evaluate(
            DecisionContext(
                original_query=query,
                rewritten_query=query,
                route="generic",
                draft_answer=answer,
                sources=[],
                attempt=1,
                conversation_context=conversation_context,
            )
        )
        self._db_logger.log_evaluation(
            run_id=run_id,
            attempt=1,
            decision=decision,
        )

        logger.info(
            "v2 generic decision %s",
            json.dumps(
                {
                    "route": "generic",
                    "confidence": decision.confidence,
                    "verdict": decision.verdict,
                    "correct_route": decision.correct_route,
                }
            ),
        )

        if decision.correct_route == "rag":
            escalated = GateResult(
                route="rag",
                reason=(
                    f"Escalated from generic gate: {decision.feedback or gate_result.reason}"
                ),
                llm_call=None,
            )
            self._db_logger.log_gate(
                run_id=run_id,
                gate_result=escalated,
            )
            return self._run_rag_pipeline(
                run_id=run_id,
                stripped=query,
                gate_result=escalated,
                conv_state=conv_state,
                conversation_context=conversation_context,
                modality_filter=modality_filter,
            )

        updated_conversation = self._memory.record_exchange(conv_state, query, answer)
        return self._build_response(
            query=query,
            rewritten_query=query,
            gate_result=gate_result,
            modality_filter=modality_filter,
            answer=answer,
            sources=[],
            attempts=1,
            confidence=decision.confidence,
            disclaimer_appended=False,
            conversation=updated_conversation,
        )

    def _run_rag_pipeline(
        self,
        run_id: UUID | None,
        stripped: str,
        *,
        gate_result: GateResult,
        conv_state: ConversationState,
        conversation_context: str,
        modality_filter: FileModality | None,
    ) -> SearchV2Response:
        max_attempts = max(1, self._settings.v2_max_pipeline_attempts)
        threshold = self._settings.v2_confidence_threshold

        prev_feedback: str | None = None
        rewritten_text = stripped
        answer = ""
        sources: list[SearchSource] = []
        confidence: float | None = None

        for attempt in range(1, max_attempts + 1):
            rewritten = self._rewriter.rewrite(
                stripped,
                prev_feedback,
                conversation_context=conversation_context,
            )
            rewritten_text = rewritten.text
            self._db_logger.log_rewrite(
                run_id=run_id,
                attempt=attempt,
                rewritten=rewritten,
            )

            sources = self._rrf.retrieve(
                rewritten_text,
                modality_filter=modality_filter,
            )
            self._db_logger.log_retrieval(
                run_id=run_id,
                attempt=attempt,
                query=stripped,
                rewritten_query=rewritten_text,
                sources=sources,
            )

            if not sources:
                answer = NO_INDEXED_CONTENT
                from app.services.v2.rag_synthesis_agent import SynthesisResult
                mock_result = SynthesisResult(answer=answer, llm_call=None)
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=mock_result,
                )
            else:
                synthesis_result = self._rag_synthesis.synthesize(
                    stripped,
                    sources,
                    conversation_context=conversation_context,
                )
                answer = synthesis_result.answer
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=synthesis_result,
                )

            decision = self._decision.evaluate(
                DecisionContext(
                    original_query=stripped,
                    rewritten_query=rewritten_text,
                    route="rag",
                    draft_answer=answer,
                    sources=sources,
                    attempt=attempt,
                    conversation_context=conversation_context,
                )
            )
            confidence = decision.confidence
            self._db_logger.log_evaluation(
                run_id=run_id,
                attempt=attempt,
                decision=decision,
            )

            logger.info(
                "v2 pipeline attempt %s",
                json.dumps(
                    {
                        "attempt": attempt,
                        "route": "rag",
                        "confidence": decision.confidence,
                        "verdict": decision.verdict,
                        "correct_route": decision.correct_route,
                        "source_count": len(sources),
                    }
                ),
            )

            if decision.confidence >= threshold and decision.verdict == "good":
                updated_conversation = self._memory.record_exchange(
                    conv_state, stripped, answer
                )
                return self._build_response(
                    query=stripped,
                    rewritten_query=rewritten_text,
                    gate_result=gate_result,
                    modality_filter=modality_filter,
                    answer=answer,
                    sources=sources,
                    attempts=attempt,
                    confidence=confidence,
                    disclaimer_appended=False,
                    conversation=updated_conversation,
                )

            if attempt < max_attempts:
                prev_feedback = decision.feedback or "Improve query specificity and keywords."
                continue

            final_answer = answer
            if LOW_CONFIDENCE_DISCLAIMER not in final_answer:
                final_answer = f"{final_answer.rstrip()}\n\n{LOW_CONFIDENCE_DISCLAIMER}"

            updated_conversation = self._memory.record_exchange(
                conv_state, stripped, final_answer
            )
            return self._build_response(
                query=stripped,
                rewritten_query=rewritten_text,
                gate_result=gate_result,
                modality_filter=modality_filter,
                answer=final_answer,
                sources=sources,
                attempts=attempt,
                confidence=confidence,
                disclaimer_appended=True,
                conversation=updated_conversation,
            )

        updated_conversation = self._memory.record_exchange(conv_state, stripped, answer)
        return self._build_response(
            query=stripped,
            rewritten_query=rewritten_text,
            gate_result=gate_result,
            modality_filter=modality_filter,
            answer=answer,
            sources=sources,
            attempts=max_attempts,
            confidence=confidence,
            disclaimer_appended=False,
            conversation=updated_conversation,
        )

    @staticmethod
    def _build_response(
        *,
        query: str,
        rewritten_query: str,
        gate_result: GateResult,
        modality_filter: FileModality | None,
        answer: str,
        sources: list[SearchSource],
        attempts: int,
        confidence: float | None,
        disclaimer_appended: bool,
        conversation: ConversationState,
    ) -> SearchV2Response:
        return SearchV2Response(
            query=query,
            rewritten_query=rewritten_query,
            route=SearchV2Route(gate_result.route),
            gate_reason=gate_result.reason,
            modality_filter=modality_filter,
            answer=answer,
            sources=sources,
            attempts=attempts,
            confidence=confidence,
            disclaimer_appended=disclaimer_appended,
            conversation=conversation,
        )