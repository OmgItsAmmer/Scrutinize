import json
import logging
import typing
from uuid import UUID

from langsmith import traceable

from sqlmodel import Session

from app.core.config import Settings
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.schemas.v2.project import ProjectContext
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

    @traceable(name="search_v2", run_type="chain")
    def search(
        self,
        query: str,
        *,
        project_ctx: ProjectContext | None = None,
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
            model=project_ctx.gate_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("gate") if project_ctx else None
            ),
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
                project_ctx=project_ctx,
            )
        else:
            response = self._run_rag_pipeline(
                run_id=run_id,
                stripped=stripped,
                gate_result=gate_result,
                conv_state=conv_state,
                conversation_context=conversation_context,
                modality_filter=modality_filter,
                project_ctx=project_ctx,
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

    def search_stream(
        self,
        query: str,
        *,
        project_ctx: ProjectContext | None = None,
        modality_filter: FileModality | None = None,
        conversation: ConversationState | None = None,
    ) -> typing.Generator[str, None, None]:
        import json
        from uuid import UUID

        def emit(event: str, data: dict):
            payload = json.dumps({"event": event, "data": data}, default=str)
            return f"data: {payload}\n\n"

        stripped = query.strip()
        conv_state, conversation_context = self._memory.prepare(conversation)

        run_id = self._db_logger.start_run(
            query=stripped,
            modality_filter=modality_filter,
            conversation_context=conversation_context,
        )

        gate_model = project_ctx.gate_model if project_ctx else self._settings.local_llm_gate_model
        yield emit("status", {
            "step": "gate",
            "model": gate_model,
            "message": "Classifying query route..."
        })

        gate_result = self._gate.classify(
            stripped,
            model=project_ctx.gate_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("gate") if project_ctx else None
            ),
            conversation_context=conversation_context,
        )
        self._db_logger.log_gate(
            run_id=run_id,
            gate_result=gate_result,
        )

        yield emit("status", {
            "step": "gate_end",
            "route": gate_result.route,
            "message": f"Route decided: {gate_result.route.upper()}"
        })

        if gate_result.route == "generic":
            answer = ""
            if gate_result.reply:
                answer = gate_result.reply
                yield emit("status", {
                    "step": "synthesis",
                    "model": gate_model,
                    "message": "Retrieving cached reply..."
                })
                yield emit("chunk", {"text": answer})
            else:
                yield emit("status", {
                    "step": "synthesis",
                    "model": gate_model,
                    "message": "Generating reply..."
                })
                for chunk in self._generic.reply_stream(
                    stripped,
                    system_override=project_ctx.system_prompt_overrides.get("generic") if project_ctx else None,
                    conversation_context=conversation_context,
                ):
                    answer += chunk
                    yield emit("chunk", {"text": chunk})

            yield emit("status", {
                "step": "evaluation",
                "model": project_ctx.decision_model if project_ctx else self._settings.local_llm_decision_model,
                "message": "Evaluating reply..."
            })
            
            from app.services.v2.generic_agent import GenericReplyResult
            self._db_logger.log_synthesis(
                run_id=run_id,
                attempt=1,
                synthesis_result=GenericReplyResult(answer=answer, llm_call=None),
            )

            decision = self._decision.evaluate(
                DecisionContext(
                    original_query=stripped,
                    rewritten_query=stripped,
                    route="generic",
                    draft_answer=answer,
                    sources=[],
                    attempt=1,
                    conversation_context=conversation_context,
                ),
                model=project_ctx.decision_model if project_ctx else None,
                system_override=project_ctx.system_prompt_overrides.get("decision") if project_ctx else None,
            )
            self._db_logger.log_evaluation(
                run_id=run_id,
                attempt=1,
                decision=decision,
            )

            yield emit("status", {
                "step": "evaluation_end",
                "confidence": decision.confidence,
                "verdict": decision.verdict,
                "correct_route": decision.correct_route,
                "message": f"Evaluation verdict: {decision.verdict.upper()} (Confidence: {int((decision.confidence or 0)*100)}%)"
            })

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
                yield emit("status", {
                    "step": "escalate",
                    "message": "Generic response evaluation failed. Escalating to RAG pipeline..."
                })
                yield from self._stream_rag_pipeline(
                    run_id=run_id,
                    stripped=stripped,
                    gate_result=escalated,
                    conv_state=conv_state,
                    conversation_context=conversation_context,
                    modality_filter=modality_filter,
                    project_ctx=project_ctx,
                    emit=emit,
                )
                return

            updated_conversation = self._memory.record_exchange(conv_state, stripped, answer)
            response = self._build_response(
                query=stripped,
                rewritten_query=stripped,
                gate_result=gate_result,
                modality_filter=modality_filter,
                answer=answer,
                sources=[],
                attempts=1,
                confidence=decision.confidence,
                disclaimer_appended=False,
                conversation=updated_conversation,
            )
            self._db_logger.end_run(
                run_id=run_id,
                final_route=response.route,
                final_answer=response.answer,
                final_confidence=response.confidence,
                attempts_count=response.attempts,
                disclaimer_appended=response.disclaimer_appended,
            )
            yield emit("result", response.model_dump(mode="json"))
            return

        else:
            yield from self._stream_rag_pipeline(
                run_id=run_id,
                stripped=stripped,
                gate_result=gate_result,
                conv_state=conv_state,
                conversation_context=conversation_context,
                modality_filter=modality_filter,
                project_ctx=project_ctx,
                emit=emit,
            )

    def _stream_rag_pipeline(
        self,
        run_id: UUID | None,
        stripped: str,
        *,
        gate_result: GateResult,
        conv_state: ConversationState,
        conversation_context: str,
        modality_filter: FileModality | None,
        project_ctx: ProjectContext | None,
        emit,
    ) -> typing.Generator[str, None, None]:
        max_attempts = (
            project_ctx.max_attempts if project_ctx else max(1, self._settings.v2_max_pipeline_attempts)
        )
        threshold = (
            project_ctx.confidence_threshold if project_ctx else self._settings.v2_confidence_threshold
        )
        project_id = project_ctx.project_id if project_ctx else UUID(int=0)

        prev_feedback: str | None = None
        rewritten_text = stripped
        answer = ""
        sources: list[SearchSource] = []
        confidence: float | None = None

        for attempt in range(1, max_attempts + 1):
            rewriter_model = project_ctx.rewriter_model if project_ctx else self._settings.local_llm_rewriter_model
            yield emit("status", {
                "step": "rewrite",
                "model": rewriter_model,
                "message": f"Rewriting search query (attempt {attempt}/{max_attempts})..."
            })

            rewritten = self._rewriter.rewrite(
                stripped,
                prev_feedback,
                model=project_ctx.rewriter_model if project_ctx else None,
                system_override=project_ctx.system_prompt_overrides.get("rewriter") if project_ctx else None,
                conversation_context=conversation_context,
            )
            rewritten_text = rewritten.text
            self._db_logger.log_rewrite(
                run_id=run_id,
                attempt=attempt,
                rewritten=rewritten,
            )

            yield emit("status", {
                "step": "rewrite_end",
                "rewritten": rewritten_text,
                "message": f"Search terms optimized: \"{rewritten_text}\""
            })

            yield emit("status", {
                "step": "retrieval",
                "message": "Retrieving context from indexed sources..."
            })

            retrieval = self._rrf.retrieve(
                rewritten_text,
                project_id=project_id,
                modality_filter=modality_filter,
            )
            sources = retrieval.sources
            self._db_logger.log_retrieval(
                run_id=run_id,
                attempt=attempt,
                query=stripped,
                rewritten_query=rewritten_text,
                sources=sources,
                retrieval_stats=retrieval.stats,
                source_rank_fields=retrieval.source_rank_fields,
                latency_ms=retrieval.latency_ms,
            )

            yield emit("status", {
                "step": "retrieval_end",
                "sources_count": len(sources),
                "sources": [s.model_dump(mode="json") for s in sources],
                "message": f"Found {len(sources)} relevant document matches."
            })

            if not sources:
                answer = NO_INDEXED_CONTENT
                yield emit("status", {
                    "step": "synthesis",
                    "message": "No documents found. Synthesizing default response..."
                })
                yield emit("chunk", {"text": answer})
                from app.services.v2.rag_synthesis_agent import SynthesisResult
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=SynthesisResult(answer=answer, llm_call=None),
                )
            else:
                synthesis_model = project_ctx.synthesis_model if project_ctx else self._settings.local_llm_rewriter_model
                yield emit("status", {
                    "step": "synthesis",
                    "model": synthesis_model,
                    "message": "Synthesizing answer..."
                })

                answer = ""
                for chunk in self._rag_synthesis.synthesize_stream(
                    stripped,
                    sources,
                    model=project_ctx.synthesis_model if project_ctx else None,
                    system_override=(
                        project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                    ),
                    conversation_context=conversation_context,
                ):
                    answer += chunk
                    yield emit("chunk", {"text": chunk})

                from app.services.v2.rag_synthesis_agent import SynthesisResult
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=SynthesisResult(answer=answer, llm_call=None),
                )

            decision_model = project_ctx.decision_model if project_ctx else self._settings.local_llm_decision_model
            yield emit("status", {
                "step": "decision",
                "model": decision_model,
                "message": "Evaluating generated answer content..."
            })

            decision = self._decision.evaluate(
                DecisionContext(
                    original_query=stripped,
                    rewritten_query=rewritten_text,
                    route="rag",
                    draft_answer=answer,
                    sources=sources,
                    attempt=attempt,
                    conversation_context=conversation_context,
                ),
                model=project_ctx.decision_model if project_ctx else None,
                system_override=project_ctx.system_prompt_overrides.get("decision") if project_ctx else None,
            )
            confidence = decision.confidence
            self._db_logger.log_evaluation(
                run_id=run_id,
                attempt=attempt,
                decision=decision,
            )

            yield emit("status", {
                "step": "evaluation_end",
                "confidence": confidence,
                "verdict": decision.verdict,
                "correct_route": decision.correct_route,
                "message": f"Answer verified: {decision.verdict.upper()} (Confidence: {int((confidence or 0)*100)}%)"
            })

            if decision.confidence >= threshold and decision.verdict == "good":
                updated_conversation = self._memory.record_exchange(
                    conv_state, stripped, answer
                )
                response = self._build_response(
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
                self._db_logger.end_run(
                    run_id=run_id,
                    final_route=response.route,
                    final_answer=response.answer,
                    final_confidence=response.confidence,
                    attempts_count=response.attempts,
                    disclaimer_appended=response.disclaimer_appended,
                )
                yield emit("result", response.model_dump(mode="json"))
                return

            if attempt < max_attempts:
                prev_feedback = decision.feedback or "Improve query specificity and keywords."
                yield emit("status", {
                    "step": "retry",
                    "feedback": prev_feedback,
                    "message": f"Confidence below threshold. Retrying with feedback: {prev_feedback}"
                })
                answer = ""
                continue

            final_answer = answer
            if LOW_CONFIDENCE_DISCLAIMER not in final_answer:
                final_answer = f"{final_answer.rstrip()}\n\n{LOW_CONFIDENCE_DISCLAIMER}"

            updated_conversation = self._memory.record_exchange(
                conv_state, stripped, final_answer
            )
            response = self._build_response(
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
            self._db_logger.end_run(
                run_id=run_id,
                final_route=response.route,
                final_answer=response.answer,
                final_confidence=response.confidence,
                attempts_count=response.attempts,
                disclaimer_appended=response.disclaimer_appended,
            )
            yield emit("result", response.model_dump(mode="json"))
            return

    @traceable(name="handle_generic_path", run_type="chain")
    def _handle_generic_path(
        self,
        *,
        run_id: UUID | None,
        query: str,
        gate_result: GateResult,
        conv_state: ConversationState,
        modality_filter: FileModality | None,
        conversation_context: str,
        project_ctx: ProjectContext | None = None,
    ) -> SearchV2Response:
        if gate_result.reply:
            answer = gate_result.reply
        else:
            generic_result = self._generic.reply(
                query,
                system_override=project_ctx.system_prompt_overrides.get("generic") if project_ctx else None,
                conversation_context=conversation_context,
            )
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
            ),
            model=project_ctx.decision_model if project_ctx else None,
            system_override=project_ctx.system_prompt_overrides.get("decision") if project_ctx else None,
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
                project_ctx=project_ctx,
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

    @traceable(name="run_rag_pipeline", run_type="chain")
    def _run_rag_pipeline(
        self,
        run_id: UUID | None,
        stripped: str,
        *,
        gate_result: GateResult,
        conv_state: ConversationState,
        conversation_context: str,
        modality_filter: FileModality | None,
        project_ctx: ProjectContext | None = None,
    ) -> SearchV2Response:
        max_attempts = (
            project_ctx.max_attempts if project_ctx else max(1, self._settings.v2_max_pipeline_attempts)
        )
        threshold = (
            project_ctx.confidence_threshold if project_ctx else self._settings.v2_confidence_threshold
        )
        # Sentinel project_id when no context provided (legacy / un-tenanted call)
        project_id = project_ctx.project_id if project_ctx else UUID(int=0)

        prev_feedback: str | None = None
        rewritten_text = stripped
        answer = ""
        sources: list[SearchSource] = []
        confidence: float | None = None

        for attempt in range(1, max_attempts + 1):
            rewritten = self._rewriter.rewrite(
                stripped,
                prev_feedback,
                model=project_ctx.rewriter_model if project_ctx else None,
                system_override=project_ctx.system_prompt_overrides.get("rewriter") if project_ctx else None,
                conversation_context=conversation_context,
            )
            rewritten_text = rewritten.text
            self._db_logger.log_rewrite(
                run_id=run_id,
                attempt=attempt,
                rewritten=rewritten,
            )

            retrieval = self._rrf.retrieve(
                rewritten_text,
                project_id=project_id,
                modality_filter=modality_filter,
            )
            sources = retrieval.sources
            self._db_logger.log_retrieval(
                run_id=run_id,
                attempt=attempt,
                query=stripped,
                rewritten_query=rewritten_text,
                sources=sources,
                retrieval_stats=retrieval.stats,
                source_rank_fields=retrieval.source_rank_fields,
                latency_ms=retrieval.latency_ms,
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
                    model=project_ctx.synthesis_model if project_ctx else None,
                    system_override=(
                        project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                    ),
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
                ),
                model=project_ctx.decision_model if project_ctx else None,
                system_override=project_ctx.system_prompt_overrides.get("decision") if project_ctx else None,
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
                        "retrieval": retrieval.stats.to_dict(),
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