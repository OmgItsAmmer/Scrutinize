import json
import logging
import os
import typing
from typing import Any
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
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent, SynthesisResult as RagSynthesisResult
from app.services.v2.rrf_retriever import RrfRetriever
from app.services.v2.mcp_manager import McpClientManager
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

NO_INDEXED_CONTENT = "No matching indexed content found."
LOW_CONFIDENCE_DISCLAIMER = "Note: answer may vary — retrieval confidence was low."
PDF_TITLE_FALLBACK = "generated-document"
PDF_TOOL_NAME = "generate_pdf"


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
        web_search: WebSearchService | None = None,
        mcp_manager: McpClientManager | None = None,
        session: Session | None = None,
    ) -> None:
        self._rewriter = rewriter
        self._gate = gate
        self._generic = generic_agent
        self._rrf = rrf_retriever
        self._rag_synthesis = rag_synthesis
        self._decision = decision_agent
        self._memory = conversation_memory
        self._web_search = web_search
        self._mcp_manager = mcp_manager
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
        web_search: bool = False,
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
            tool_context=self._build_gate_tool_context(),
        )

        if web_search:
            from app.services.v2.rag_gate import GateResult
            new_route = "hybrid" if gate_result.route == "rag" else ("web" if gate_result.route == "generic" else gate_result.route)
            gate_result = GateResult(
                route=new_route,
                reason=f"{gate_result.reason} (Web search forced by user)",
                reply=None if new_route != "generic" else gate_result.reply,
                requested_tool=gate_result.requested_tool,
                llm_call=gate_result.llm_call
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
        web_search: bool = False,
    ) -> typing.Generator[str, None, None]:
        import json
        from uuid import UUID

        def emit(event: str, data: dict):
            payload = json.dumps({"event": event, "data": data}, default=str)
            return f"data: {payload}\n\n"

        stripped = query.strip()
        conv_state, conversation_context = self._memory.prepare(conversation)

        run_id: UUID | None = None
        try:
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
                tool_context=self._build_gate_tool_context(),
            )

            if web_search:
                from app.services.v2.rag_gate import GateResult
                new_route = "hybrid" if gate_result.route == "rag" else ("web" if gate_result.route == "generic" else gate_result.route)
                gate_result = GateResult(
                    route=new_route,
                    reason=f"{gate_result.reason} (Web search forced by user)",
                    reply=None if new_route != "generic" else gate_result.reply,
                    requested_tool=gate_result.requested_tool,
                    llm_call=gate_result.llm_call
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
        except Exception as exc:
            logger.exception("v2 stream failed: %s", exc)
            if run_id is not None:
                try:
                    self._db_logger.end_run(
                        run_id=run_id,
                        final_route="generic" if "generic" in str(exc).lower() else "rag",
                        final_answer=f"Error: {exc}",
                        final_confidence=None,
                        attempts_count=1,
                        disclaimer_appended=False,
                    )
                except Exception:
                    logger.exception("Failed to close run after stream error")
            yield emit("error", {"message": str(exc)})
            return

    def _build_gate_tool_context(self) -> str:
        if not self._mcp_manager or not self._mcp_manager.is_enabled():
            return ""
        return (
            "- generate_pdf: Create a downloadable PDF document from synthesized "
            "technology/AI news content."
        )

    @staticmethod
    def _requested_pdf(gate_result: GateResult) -> bool:
        return gate_result.requested_tool == PDF_TOOL_NAME

    def _build_pdf_download_url(self, filename: str) -> str:
        base_url = os.getenv("VITE_API_URL", "http://localhost:8000").rstrip("/")
        return f"{base_url}/v2/pdf/download/{filename}"

    def _build_pdf_success_message(self, filename: str, download_url: str) -> str:
        return f"PDF generated successfully: [{filename}]({download_url})"

    def _slugify_pdf_title(self, value: str) -> str:
        cleaned_chars = [
            character.lower() if character.isalnum() else "-"
            for character in value.strip()
        ]
        cleaned = "".join(cleaned_chars).strip("-")
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned[:40] or PDF_TITLE_FALLBACK

    def _generate_pdf_title(self, query: str, answer: str) -> str:
        if not self._settings.pdf_renamer_configured:
            return self._slugify_pdf_title(query)

        prompt = (
            "You are a filename renaming assistant.\n"
            "Create a short PDF filename slug from the content.\n"
            "Rules:\n"
            "- Return only the slug, no quotes, no punctuation, no markdown.\n"
            "- Use lowercase words separated by hyphens.\n"
            "- Keep it under 6 words.\n"
            "- Prefer the main topic of the content.\n"
        )
        user = (
            f"User request: {query.strip()}\n\n"
            f"Content:\n{answer.strip() or query.strip()}\n\n"
            "Filename slug:"
        )

        try:
            import httpx

            response = httpx.post(
                f"{self._settings.pdf_renamer_base_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": self._settings.pdf_renamer_model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                    "stream": False,
                },
                timeout=self._settings.pdf_renamer_timeout_s,
            )
            response.raise_for_status()
            body = response.json()
            slug = str(body["choices"][0]["message"].get("content") or "").strip()
            return self._slugify_pdf_title(slug)
        except Exception:
            return self._slugify_pdf_title(query)

    def _generate_pdf_from_answer(self, query: str, answer: str) -> tuple[str, str] | None:
        if not self._mcp_manager or not self._mcp_manager.is_enabled():
            return None

        title_slug = self._generate_pdf_title(query, answer)

        filepath = self._mcp_manager.call_tool(
            "generate_pdf",
            {
                "title": title_slug,
                "content": answer.strip() or query.strip(),
            },
        )
        filename = os.path.basename(str(filepath).strip())
        if not filename:
            return None
        return filename, self._build_pdf_download_url(filename)

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

            sources, stats, rank_fields, latency_ms = self._retrieve_sources(
                rewritten_text=rewritten_text,
                project_id=project_id,
                modality_filter=modality_filter,
                route=gate_result.route,
            )
            self._db_logger.log_retrieval(
                run_id=run_id,
                attempt=attempt,
                query=stripped,
                rewritten_query=rewritten_text,
                sources=sources,
                retrieval_stats=stats,
                source_rank_fields=rank_fields,
                latency_ms=latency_ms,
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
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=RagSynthesisResult(answer=answer, llm_call=None),
                )
            else:
                synthesis_model = project_ctx.synthesis_model if project_ctx else self._settings.local_llm_rewriter_model
                yield emit("status", {
                    "step": "synthesis",
                    "model": synthesis_model,
                    "message": "Synthesizing answer..."
                })

                pdf_requested = self._requested_pdf(gate_result)
                tools = (
                    self._mcp_manager.list_tools()
                    if (
                        self._mcp_manager
                        and self._mcp_manager.is_enabled()
                    )
                    else None
                )
                if tools or pdf_requested:
                    synthesis_result = self._rag_synthesis.synthesize(
                        stripped,
                        sources,
                        model=project_ctx.synthesis_model if project_ctx else None,
                        system_override=(
                            project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                        ),
                        conversation_context=conversation_context,
                        tools=tools,
                    )
                    answer = synthesis_result.answer

                    llm_call = synthesis_result.llm_call
                    pdf_result = None
                    if llm_call and llm_call.tool_calls:
                        for tool_call in llm_call.tool_calls:
                            if tool_call.name == "generate_pdf":
                                try:
                                    yield emit("status", {
                                        "step": "tool_call",
                                        "message": f"Running tool: {tool_call.name}..."
                                    })
                                    filepath = self._mcp_manager.call_tool(tool_call.name, tool_call.arguments)
                                    filename = os.path.basename(str(filepath).strip())
                                    download_url = self._build_pdf_download_url(filename)
                                    yield emit("status", {
                                        "step": "tool_call_end",
                                        "message": f"PDF generated successfully: {filename}"
                                    })
                                    answer = self._build_pdf_success_message(filename, download_url)
                                    pdf_result = (filename, download_url)
                                except Exception as e:
                                    answer = f"Failed to generate PDF: {e}"
                                    synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)
                                    pdf_result = None
                                break

                    if pdf_requested and pdf_result is None:
                        try:
                            yield emit("status", {
                                "step": "tool_call",
                                "message": "Running tool: generate_pdf..."
                            })
                            maybe_pdf = self._generate_pdf_from_answer(stripped, answer)
                            if not maybe_pdf:
                                raise RuntimeError("MCP PDF Server is unavailable or disabled.")
                            filename, download_url = maybe_pdf
                            yield emit("status", {
                                "step": "tool_call_end",
                                "message": f"PDF generated successfully: {filename}"
                            })
                            answer = self._build_pdf_success_message(filename, download_url)
                        except Exception as exc:
                            answer = f"Failed to generate PDF: {exc}"
                        synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)

                    yield emit("chunk", {"text": answer})
                else:
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
                    synthesis_result = RagSynthesisResult(answer=answer, llm_call=None)

                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=synthesis_result,
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

            sources, stats, rank_fields, latency_ms = self._retrieve_sources(
                rewritten_text=rewritten_text,
                project_id=project_id,
                modality_filter=modality_filter,
                route=gate_result.route,
            )
            self._db_logger.log_retrieval(
                run_id=run_id,
                attempt=attempt,
                query=stripped,
                rewritten_query=rewritten_text,
                sources=sources,
                retrieval_stats=stats,
                source_rank_fields=rank_fields,
                latency_ms=latency_ms,
            )

            if not sources:
                answer = NO_INDEXED_CONTENT
                mock_result = RagSynthesisResult(answer=answer, llm_call=None)
                self._db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=attempt,
                    synthesis_result=mock_result,
                )
            else:
                pdf_requested = self._requested_pdf(gate_result)
                tools = (
                    self._mcp_manager.list_tools()
                    if (
                        self._mcp_manager
                        and self._mcp_manager.is_enabled()
                    )
                    else None
                )
                synthesis_result = self._rag_synthesis.synthesize(
                    stripped,
                    sources,
                    model=project_ctx.synthesis_model if project_ctx else None,
                    system_override=(
                        project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                    ),
                    conversation_context=conversation_context,
                    tools=tools,
                )
                answer = synthesis_result.answer

                llm_call = synthesis_result.llm_call
                if llm_call and llm_call.tool_calls:
                    for tool_call in llm_call.tool_calls:
                        if tool_call.name == "generate_pdf":
                            try:
                                filepath = self._mcp_manager.call_tool(tool_call.name, tool_call.arguments)
                                filename = os.path.basename(str(filepath).strip())
                                download_url = self._build_pdf_download_url(filename)
                                answer = self._build_pdf_success_message(filename, download_url)
                                synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)
                            except Exception as e:
                                answer = f"Failed to generate PDF: {e}"
                                synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)
                            break
                if pdf_requested and not answer.startswith("PDF generated successfully:"):
                    try:
                        maybe_pdf = self._generate_pdf_from_answer(stripped, answer)
                        if not maybe_pdf:
                            raise RuntimeError("MCP PDF Server is unavailable or disabled.")
                        filename, download_url = maybe_pdf
                        answer = self._build_pdf_success_message(filename, download_url)
                    except Exception as exc:
                        answer = f"Failed to generate PDF: {exc}"
                    synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)

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

    def _retrieve_sources(
        self,
        rewritten_text: str,
        project_id: UUID,
        modality_filter: FileModality | None,
        route: str,
    ) -> tuple[list[SearchSource], Any, list[Any], int]:
        import time
        from app.services.v2.retrieval_utils import RetrievalStats

        if route == "web":
            started = time.monotonic()
            sources = self._retrieve_web(rewritten_text)
            latency_ms = int((time.monotonic() - started) * 1000)
            return sources, RetrievalStats.empty(rrf_k=self._settings.v2_rrf_k), [], latency_ms

        # Run RRF retrieval
        retrieval = self._rrf.retrieve(
            rewritten_text,
            project_id=project_id,
            modality_filter=modality_filter,
        )
        sources = retrieval.sources
        stats = retrieval.stats
        rank_fields = retrieval.source_rank_fields
        latency_ms = retrieval.latency_ms

        if route == "hybrid":
            started_web = time.monotonic()
            web_sources = self._retrieve_web(rewritten_text)
            sources = sources + web_sources
            latency_ms += int((time.monotonic() - started_web) * 1000)
        elif not sources and self._settings.enable_web_search:
            # Fallback to web search
            started_web = time.monotonic()
            web_sources = self._retrieve_web(rewritten_text)
            sources = web_sources
            latency_ms += int((time.monotonic() - started_web) * 1000)

        return sources, stats, rank_fields, latency_ms

    def _retrieve_web(self, query: str) -> list[SearchSource]:
        if not self._web_search:
            return []

        # 1. Search the web
        web_results = self._run_async(self._web_search.search, query, limit=3)
        if not web_results:
            return []

        # 2. Extract URLs, titles, and snippets
        urls = [res["url"] for res in web_results]
        titles = [res["title"] for res in web_results]
        snippets = [res["snippet"] for res in web_results]

        # 3. Scrape the content in parallel
        scraped_contents = self._run_async(self._web_search.scrape_urls_parallel, urls)

        # 4. Convert to SearchSource objects
        import uuid
        from app.models.file import FileModality

        sources = []
        for i, url in enumerate(urls):
            # Generate deterministic UUIDs from URL to maintain consistency
            ns = uuid.NAMESPACE_URL
            seg_id = uuid.uuid5(ns, url)
            file_id = uuid.uuid5(ns, url + "/file")
            
            content = scraped_contents[i].strip() if i < len(scraped_contents) else ""
            # Fall back to snippet if scraping yielded no content
            if not content:
                content = snippets[i]

            # Limit length to avoid breaking context window
            if len(content) > 8000:
                content = content[:8000] + "..."

            sources.append(
                SearchSource(
                    segment_id=seg_id,
                    file_id=file_id,
                    modality=FileModality.TEXT,
                    title=titles[i] or "Web Result",
                    content=content,
                    source_path=url,
                    score=1.0 - (i * 0.1),
                )
            )
        return sources

    def _run_async(self, func, *args, **kwargs):
        import asyncio
        try:
            from anyio.from_thread import run as anyio_run
            return anyio_run(func, *args, **kwargs)
        except Exception:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
                return future.result()
            else:
                return asyncio.run(func(*args, **kwargs))
