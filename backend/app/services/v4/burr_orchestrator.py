import asyncio
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Generator
from uuid import UUID

from burr.core import ApplicationBuilder, State, default, expr
from burr.core.action import SingleStepAction
from langsmith import traceable

from app.core.config import Settings
from app.services.v4.run_budget import RunBudget, BudgetExceededError
from app.models.file import FileModality
from app.schemas.search import SearchSource
from app.schemas.v2.project import ProjectContext
from app.schemas.v2.search import ConversationState, SearchV2Response, SearchV2Route
from app.schemas.v4.rag import GateResult
from app.services.v2.conversation_memory import ConversationMemory
from app.services.v2.decision_agent import DecisionAgent, DecisionContext
from app.services.v2.generic_agent import GenericAgent, GenericReplyResult
from app.services.v2.mcp_manager import McpClientManager
from app.services.v2.pipeline_logger import PipelineLogger
from app.services.v2.query_rewriter import QueryRewriter
from app.services.v2.rag_gate import Route as LegacyRoute
from app.services.v2.rag_synthesis_agent import RagSynthesisAgent, SynthesisResult as RagSynthesisResult
from app.services.v2.retrieval_precheck import RetrievalPrecheck
from app.services.v2.rrf_retriever import RrfRetriever
from app.services.v4.rag_gate import RagGate
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

NO_INDEXED_CONTENT = "No matching indexed content found."
LOW_CONFIDENCE_DISCLAIMER = "Note: answer may vary — retrieval confidence was low."
PDF_TITLE_FALLBACK = "generated-document"
PDF_TOOL_NAME = "generate_pdf"
FLOWCHART_TOOL_NAME = "generate_flowchart"
TOOLS_REQUIRING_RAG = frozenset({PDF_TOOL_NAME, FLOWCHART_TOOL_NAME})


class PrecheckAction(SingleStepAction):
    def __init__(self, precheck: RetrievalPrecheck | None, settings: Settings):
        super().__init__()
        self.precheck = precheck
        self.settings = settings

    @property
    def reads(self) -> list[str]:
        return ["query", "project_id", "conversation_id", "has_corpus", "client_requested_tool"]

    @property
    def writes(self) -> list[str]:
        return ["route", "precheck_action", "precheck_reason"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        if self.precheck is None:
            return {"action": "continue"}, state.update(
                precheck_action="continue", precheck_reason=None
            )

        precheck_res = self.precheck.evaluate(
            state["query"],
            project_id=state["project_id"],
            conversation_id=state["conversation_id"],
            has_corpus=state["has_corpus"],
            client_requested_tool=state["client_requested_tool"],
            enable_web_search=self.settings.enable_web_search,
        )

        route = None
        if precheck_res.action == "route_rag":
            route = "rag"
        elif precheck_res.action == "route_web":
            route = "web"
        elif precheck_res.action == "route_generic":
            route = "generic"

        return {
            "precheck_action": precheck_res.action,
            "precheck_reason": precheck_res.reason,
            "route": route,
        }, state.update(
            route=route,
            precheck_action=precheck_res.action,
            precheck_reason=precheck_res.reason,
        )


class GateAction(SingleStepAction):
    def __init__(self, gate: RagGate, settings: Settings, mcp_manager: McpClientManager | None):
        super().__init__()
        self.gate = gate
        self.settings = settings
        self.mcp_manager = mcp_manager

    @property
    def reads(self) -> list[str]:
        return [
            "query",
            "route",
            "precheck_reason",
            "conversation_context",
            "client_requested_tool",
            "use_cloud_llm",
            "project_ctx",
            "llm_calls",
            "input_tokens",
        ]

    @property
    def writes(self) -> list[str]:
        return ["route", "gate_result", "llm_calls", "input_tokens"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        # If precheck already determined the route, we skip gate classification
        if state["route"] is not None:
            gate_res = GateResult(
                route=state["route"],
                reason=state["precheck_reason"] or "Retrieval pre-check forced route.",
                requested_tool=state["client_requested_tool"],
                reply=None,
            )
            return {"route": state["route"]}, state.update(gate_result=gate_res)

        project_ctx = state["project_ctx"]

        # Build tool context
        tools = []
        if self.mcp_manager and self.mcp_manager.is_enabled():
            tools.append(
                "- generate_pdf: Create a downloadable PDF document from synthesized "
                "project content."
            )
            tools.append(
                "- generate_flowchart: Generate a Mermaid flowchart diagram visualizing "
                "processes/workflows."
            )
        if self.settings.enable_web_search:
            tools.append(
                "- web_search: Search the web for real-time technology/AI news, startup funding, or recent tech developments."
            )
        tool_context = "\n".join(tools)

        # Estimate input tokens before calling LLM
        prompt_len = len(state["query"]) + len(tool_context) + len(state["conversation_context"])

        gate_res = self.gate.classify(
            state["query"],
            use_cloud_llm=state["use_cloud_llm"],
            model=project_ctx.gate_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("gate") if project_ctx else None
            ),
            conversation_context=state["conversation_context"],
            tool_context=tool_context,
            client_requested_tool=state["client_requested_tool"],
        )

        # Apply web search mode overrides if any
        web_search_mode = inputs.get("web_search_mode", "auto")
        if web_search_mode == "always":
            new_route = (
                "hybrid"
                if gate_res.route == "rag"
                else ("web" if gate_res.route == "generic" else gate_res.route)
            )
            gate_res = GateResult(
                route=new_route,
                reason=f"{gate_res.reason} (Web search mode: ALWAYS)",
                reply=None if new_route != "generic" else gate_res.reply,
                requested_tool=gate_res.requested_tool,
            )
        elif web_search_mode == "never":
            new_route = "rag" if gate_res.route in ("web", "hybrid") else gate_res.route
            gate_res = GateResult(
                route=new_route,
                reason=f"{gate_res.reason} (Web search mode: NEVER)",
                reply=gate_res.reply,
                requested_tool=gate_res.requested_tool,
            )

        # Maybe force RAG for tools
        tool = gate_res.requested_tool or state["client_requested_tool"]
        if tool in TOOLS_REQUIRING_RAG:
            if gate_res.route != "rag":
                gate_res = GateResult(
                    route="rag",
                    reason=f"{gate_res.reason} ({tool} requires retrieval before document generation.)",
                    reply=None,
                    requested_tool=tool,
                )

        llm_calls = state.get("llm_calls", 0) + 1
        input_tokens = state.get("input_tokens", 0) + (prompt_len // 4 + 200)

        return {"route": gate_res.route}, state.update(
            route=gate_res.route,
            gate_result=gate_res,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
        )


class RewriteAction(SingleStepAction):
    def __init__(self, rewriter: QueryRewriter):
        super().__init__()
        self.rewriter = rewriter

    @property
    def reads(self) -> list[str]:
        return [
            "query",
            "attempt",
            "prev_feedback",
            "conversation_context",
            "project_ctx",
            "llm_calls",
            "input_tokens",
        ]

    @property
    def writes(self) -> list[str]:
        return ["rewritten_query", "llm_calls", "input_tokens"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        project_ctx = state["project_ctx"]
        rewritten = self.rewriter.rewrite(
            state["query"],
            state["prev_feedback"],
            model=project_ctx.rewriter_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("rewriter") if project_ctx else None
            ),
            conversation_context=state["conversation_context"],
        )

        prompt_len = len(state["query"]) + len(state["prev_feedback"] or "") + len(state["conversation_context"])
        llm_calls = state.get("llm_calls", 0) + 1
        input_tokens = state.get("input_tokens", 0) + (prompt_len // 4 + 300)

        return {"rewritten_query": rewritten.text}, state.update(
            rewritten_query=rewritten.text,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
        )


class RetrieveAction(SingleStepAction):
    def __init__(
        self,
        rrf_retriever: RrfRetriever,
        web_search: WebSearchService | None,
        settings: Settings,
        mcp_manager: McpClientManager | None,
    ):
        super().__init__()
        self.rrf = rrf_retriever
        self.web_search = web_search
        self.settings = settings
        self.mcp_manager = mcp_manager

    @property
    def reads(self) -> list[str]:
        return [
            "rewritten_query",
            "project_id",
            "modality_filter",
            "route",
            "conversation_id",
            "web_searches",
        ]

    @property
    def writes(self) -> list[str]:
        return ["sources", "web_searches"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        rewritten_text = state["rewritten_query"]
        project_id = state["project_id"]
        modality_filter = state["modality_filter"]
        route = state["route"]
        conversation_id = state["conversation_id"]
        web_search_mode = inputs.get("web_search_mode", "auto")

        disable_web = web_search_mode == "never"
        web_searches = state.get("web_searches", 0)

        if route == "web":
            if disable_web:
                sources = []
            else:
                sources = self._retrieve_web(rewritten_text)
                web_searches += 1
            return {"sources": sources}, state.update(sources=sources, web_searches=web_searches)

        # Run RRF retrieval
        retrieval = self.rrf.retrieve(
            rewritten_text,
            project_id=project_id,
            modality_filter=modality_filter,
            conversation_id=conversation_id,
            include_project_wide=True,
        )
        sources = retrieval.sources

        if route == "hybrid" and not disable_web:
            web_sources = self._retrieve_web(rewritten_text)
            sources = sources + web_sources
            web_searches += 1
        elif not sources and self.settings.enable_web_search and not disable_web:
            web_sources = self._retrieve_web(rewritten_text)
            sources = web_sources
            web_searches += 1

        # Rerank combined results to put the best on top
        sources.sort(key=lambda s: s.score, reverse=True)

        return {"sources": sources}, state.update(sources=sources, web_searches=web_searches)

    def _retrieve_web(self, query: str) -> list[SearchSource]:
        web_results = []
        if self.mcp_manager and self.mcp_manager.is_enabled():
            try:
                raw_json = self.mcp_manager.call_tool("web_search", {"query": query})
                web_results = json.loads(raw_json)
            except Exception as e:
                logger.warning(
                    "MCP web_search tool call failed; falling back to direct web search service: %s",
                    e,
                )

        if not web_results and self.web_search:
            direct_results = self._run_async(self.web_search.search, query, limit=3)
            if direct_results:
                urls = [res["url"] for res in direct_results]
                scraped_contents = self._run_async(self.web_search.scrape_urls_parallel, urls)
                for i, res in enumerate(direct_results):
                    content = scraped_contents[i].strip() if i < len(scraped_contents) else ""
                    if not content:
                        content = res.get("snippet", "")
                    if len(content) > 8000:
                        content = content[:8000] + "..."
                    web_results.append(
                        {
                            "title": res.get("title", "Web Result"),
                            "url": res.get("url", ""),
                            "snippet": res.get("snippet", ""),
                            "content": content,
                        }
                    )

        if not web_results:
            return []

        sources = []
        for i, res in enumerate(web_results):
            url = res.get("url", "")
            title = res.get("title", "Web Result")
            content = res.get("content", "")
            snippet = res.get("snippet", "")

            ns = uuid.NAMESPACE_URL
            seg_id = uuid.uuid5(ns, url)
            file_id = uuid.uuid5(ns, url + "/file")

            final_content = content.strip() if content else snippet.strip()
            if len(final_content) > 8000:
                final_content = final_content[:8000] + "..."

            sources.append(
                SearchSource(
                    segment_id=seg_id,
                    file_id=file_id,
                    modality=FileModality.TEXT,
                    title=title,
                    content=final_content,
                    source_path=url,
                    score=0.016 - (i * 0.002),
                )
            )
        return sources

    def _run_async(self, func, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            result = None
            exception = None

            def target():
                nonlocal result, exception
                try:
                    result = asyncio.run(func(*args, **kwargs))
                except Exception as e:
                    exception = e

            t = threading.Thread(target=target)
            t.start()
            t.join()
            if exception:
                raise exception
            return result
        else:
            return asyncio.run(func(*args, **kwargs))


class SynthesizeAction(SingleStepAction):
    def __init__(
        self,
        rag_synthesis: RagSynthesisAgent,
        settings: Settings,
        mcp_manager: McpClientManager | None,
    ):
        super().__init__()
        self.rag_synthesis = rag_synthesis
        self.settings = settings
        self.mcp_manager = mcp_manager

    @property
    def reads(self) -> list[str]:
        return [
            "query",
            "rewritten_query",
            "sources",
            "gate_result",
            "conversation_context",
            "project_ctx",
            "llm_calls",
            "input_tokens",
            "tools",
        ]

    @property
    def writes(self) -> list[str]:
        return ["answer", "llm_calls", "input_tokens", "tools"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        query = state["query"]
        rewritten_text = state["rewritten_query"]
        sources = state["sources"]
        gate_result = state["gate_result"]
        conversation_context = state["conversation_context"]
        project_ctx = state["project_ctx"]
        on_chunk = inputs.get("on_chunk")

        pdf_requested = gate_result.requested_tool == PDF_TOOL_NAME
        flowchart_requested = gate_result.requested_tool == FLOWCHART_TOOL_NAME

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        tools_count = state.get("tools", 0)

        def record_llm_call(prompt_length: int):
            nonlocal llm_calls, input_tokens
            llm_calls += 1
            input_tokens += (prompt_length // 4 + 500)

        if not sources:
            if pdf_requested:
                prompt_length = len(rewritten_text) + len(conversation_context)
                record_llm_call(prompt_length)
                answer = self._draft_document_content(
                    rewritten_text, conversation_context, project_ctx
                )
                answer = self._attach_pdf_to_answer(query, answer)
                tools_count += 1
            elif flowchart_requested:
                prompt_length = len(rewritten_text) + len(conversation_context)
                record_llm_call(prompt_length)
                answer = self._draft_document_content(
                    rewritten_text, conversation_context, project_ctx
                )
                answer = self._attach_flowchart_to_answer(query, answer)
                tools_count += 1
            else:
                answer = NO_INDEXED_CONTENT

            if on_chunk:
                on_chunk(answer)

            return {"answer": answer}, state.update(
                answer=answer,
                llm_calls=llm_calls,
                input_tokens=input_tokens,
                tools=tools_count,
            )

        # Synthesize with sources
        tools = (
            self.mcp_manager.list_tools()
            if (
                self.mcp_manager
                and self.mcp_manager.is_enabled()
                and not pdf_requested
                and not flowchart_requested
            )
            else None
        )

        sources_len = sum(len(s.content) for s in sources)
        prompt_length = len(rewritten_text) + sources_len + len(conversation_context)

        if tools or pdf_requested or flowchart_requested:
            # Run blocking synthesis to allow tool calling
            record_llm_call(prompt_length)
            synthesis_result = self.rag_synthesis.synthesize(
                rewritten_text,
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
            tool_result = None

            if llm_call and llm_call.tool_calls:
                for tool_call in llm_call.tool_calls:
                    if tool_call.name == "generate_pdf":
                        try:
                            filepath = self.mcp_manager.call_tool(
                                tool_call.name, tool_call.arguments
                            )
                            filename = os.path.basename(str(filepath).strip())
                            download_url = self._build_pdf_download_url(filename)
                            answer = self._append_pdf_download_link(
                                synthesis_result.answer, filename, download_url
                            )
                            tool_result = (filename, download_url)
                            tools_count += 1
                        except Exception as e:
                            answer = f"Failed to generate PDF: {e}"
                        break
                    elif tool_call.name == "generate_flowchart":
                        try:
                            mermaid_block = self.mcp_manager.call_tool(
                                tool_call.name, tool_call.arguments
                            )
                            answer = f"{synthesis_result.answer.strip()}\n\n{mermaid_block}"
                            tool_result = mermaid_block
                            tools_count += 1
                        except Exception as e:
                            answer = f"Failed to generate flowchart: {e}"
                        break

            if pdf_requested and tool_result is None:
                try:
                    maybe_pdf = self._generate_pdf_from_answer(query, answer)
                    if not maybe_pdf:
                        raise RuntimeError("MCP PDF Server is unavailable or disabled.")
                    filename, download_url = maybe_pdf
                    answer = self._append_pdf_download_link(answer, filename, download_url)
                    tools_count += 1
                except Exception as exc:
                    answer = f"Failed to generate PDF: {exc}"

            if flowchart_requested and tool_result is None:
                try:
                    mermaid_block = self._generate_flowchart_from_answer(query, answer)
                    if not mermaid_block:
                        raise RuntimeError("MCP Flowchart Server is unavailable or disabled.")
                    answer = f"{answer.strip()}\n\n{mermaid_block}"
                    tools_count += 1
                except Exception as exc:
                    answer = f"Failed to generate flowchart: {exc}"

            if on_chunk:
                on_chunk(answer)

        else:
            # Stream synthesis
            record_llm_call(prompt_length)
            answer = ""
            for chunk in self.rag_synthesis.synthesize_stream(
                rewritten_text,
                sources,
                model=project_ctx.synthesis_model if project_ctx else None,
                system_override=(
                    project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                ),
                conversation_context=conversation_context,
            ):
                answer += chunk
                if on_chunk:
                    on_chunk(chunk)

        return {"answer": answer}, state.update(
            answer=answer,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            tools=tools_count,
        )

    def _draft_document_content(
        self, query: str, conversation_context: str, project_ctx: ProjectContext | None = None
    ) -> str:
        generic_result = self.rag_synthesis.synthesize(
            query,
            [],
            model=project_ctx.synthesis_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
            ),
            conversation_context=conversation_context,
        )
        return generic_result.answer

    def _attach_pdf_to_answer(self, query: str, answer: str) -> str:
        if "/v2/pdf/download/" in answer:
            return answer
        try:
            maybe_pdf = self._generate_pdf_from_answer(query, answer)
            if not maybe_pdf:
                raise RuntimeError("MCP PDF Server is unavailable or disabled.")
            filename, download_url = maybe_pdf
            return self._append_pdf_download_link(answer, filename, download_url)
        except Exception as exc:
            return f"Failed to generate PDF: {exc}"

    def _attach_flowchart_to_answer(self, query: str, answer: str) -> str:
        if "```mermaid" in answer:
            return answer
        try:
            mermaid_block = self._generate_flowchart_from_answer(query, answer)
            if not mermaid_block:
                raise RuntimeError("MCP Flowchart Server is unavailable or disabled.")
            return f"{answer.strip()}\n\n{mermaid_block}"
        except Exception as exc:
            return f"Failed to generate flowchart: {exc}"

    def _generate_flowchart_from_answer(self, query: str, answer: str) -> str | None:
        if not self.mcp_manager or not self.mcp_manager.is_enabled():
            return None
        title_slug = self._slugify_pdf_title(query)
        mermaid_block = self.mcp_manager.call_tool(
            "generate_flowchart",
            {
                "title": title_slug,
                "content": answer.strip() or query.strip(),
            },
        )
        return str(mermaid_block).strip()

    def _build_pdf_download_url(self, filename: str) -> str:
        base_url = os.getenv("VITE_API_URL", "http://localhost:8000").rstrip("/")
        return f"{base_url}/v2/pdf/download/{filename}"

    def _append_pdf_download_link(self, answer: str, filename: str, download_url: str) -> str:
        body = answer.strip()
        if "/v2/pdf/download/" in body:
            return body
        if body.startswith("PDF generated successfully:"):
            body = "Your document is ready."
        elif not body:
            body = "Your document is ready."
        return f"{body}\n\n[Download PDF]({download_url})"

    def _slugify_pdf_title(self, value: str) -> str:
        cleaned_chars = [
            character.lower() if character.isalnum() else "-" for character in value.strip()
        ]
        cleaned = "".join(cleaned_chars).strip("-")
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned[:40] or PDF_TITLE_FALLBACK

    def _generate_pdf_title(self, query: str, answer: str) -> str:
        if not self.settings.pdf_renamer_configured:
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
                f"{self.settings.pdf_renamer_base_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": self.settings.pdf_renamer_model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                    "stream": False,
                },
                timeout=self.settings.pdf_renamer_timeout_s,
            )
            response.raise_for_status()
            body = response.json()
            slug = str(body["choices"][0]["message"].get("content") or "").strip()
            return self._slugify_pdf_title(slug)
        except Exception:
            return self._slugify_pdf_title(query)

    def _generate_pdf_from_answer(self, query: str, answer: str) -> tuple[str, str] | None:
        if not self.mcp_manager or not self.mcp_manager.is_enabled():
            return None
        title_slug = self._generate_pdf_title(query, answer)
        filepath = self.mcp_manager.call_tool(
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


class GenericAction(SingleStepAction):
    def __init__(self, generic_agent: GenericAgent):
        super().__init__()
        self.generic = generic_agent

    @property
    def reads(self) -> list[str]:
        return [
            "query",
            "gate_result",
            "conversation_context",
            "project_ctx",
            "llm_calls",
            "input_tokens",
        ]

    @property
    def writes(self) -> list[str]:
        return ["answer", "llm_calls", "input_tokens"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        gate_res = state["gate_result"]
        on_chunk = inputs.get("on_chunk")

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)

        if gate_res and gate_res.reply:
            answer = gate_res.reply
            if on_chunk:
                on_chunk(answer)
            return {"answer": answer}, state.update(
                answer=answer, llm_calls=llm_calls, input_tokens=input_tokens
            )

        # Stream reply
        llm_calls += 1
        prompt_len = len(state["query"]) + len(state["conversation_context"])
        input_tokens += (prompt_len // 4 + 300)

        project_ctx = state["project_ctx"]
        answer = ""
        for chunk in self.generic.reply_stream(
            state["query"],
            system_override=(
                project_ctx.system_prompt_overrides.get("generic") if project_ctx else None
            ),
            conversation_context=state["conversation_context"],
        ):
            answer += chunk
            if on_chunk:
                on_chunk(chunk)

        return {"answer": answer}, state.update(
            answer=answer, llm_calls=llm_calls, input_tokens=input_tokens
        )


class DecisionAction(SingleStepAction):
    def __init__(self, decision_agent: DecisionAgent):
        super().__init__()
        self.decision_agent = decision_agent

    @property
    def reads(self) -> list[str]:
        return [
            "query",
            "rewritten_query",
            "route",
            "answer",
            "sources",
            "attempt",
            "conversation_context",
            "project_ctx",
            "llm_calls",
            "input_tokens",
        ]

    @property
    def writes(self) -> list[str]:
        return ["verdict", "confidence", "attempt", "prev_feedback", "llm_calls", "input_tokens", "route"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        project_ctx = state["project_ctx"]
        decision = self.decision_agent.evaluate(
            DecisionContext(
                original_query=state["query"],
                rewritten_query=state["rewritten_query"],
                route=state["route"],
                draft_answer=state["answer"],
                sources=state["sources"],
                attempt=state["attempt"],
                conversation_context=state["conversation_context"],
            ),
            model=project_ctx.decision_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("decision") if project_ctx else None
            ),
        )

        llm_calls = state.get("llm_calls", 0) + 1
        sources_len = sum(len(s.content) for s in state["sources"])
        prompt_len = len(state["query"]) + len(state["rewritten_query"]) + len(state["answer"]) + sources_len
        input_tokens = state.get("input_tokens", 0) + (prompt_len // 4 + 400)

        return {
            "verdict": decision.verdict,
            "confidence": decision.confidence,
            "feedback": decision.feedback,
            "correct_route": decision.correct_route,
        }, state.update(
            verdict=decision.verdict,
            confidence=decision.confidence,
            attempt=state["attempt"] + 1,
            prev_feedback=decision.feedback or "Improve query specificity and keywords.",
            # If the decision agent corrects the route, update it
            route=decision.correct_route or state["route"],
            llm_calls=llm_calls,
            input_tokens=input_tokens,
        )


class BurrOrchestrator:
    """Orchestrates query pipeline execution using the Apache Burr state machine."""

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
        retrieval_precheck: RetrievalPrecheck | None = None,
        session: Any = None,
    ) -> None:
        self.rewriter = rewriter
        self.gate = gate
        self.generic_agent = generic_agent
        self.rrf_retriever = rrf_retriever
        self.rag_synthesis = rag_synthesis
        self.decision_agent = decision_agent
        self.conversation_memory = conversation_memory
        self.settings = settings
        self.web_search = web_search
        self.mcp_manager = mcp_manager
        self.retrieval_precheck = retrieval_precheck
        self.db_logger = PipelineLogger(session)

    def build_application(self, initial_state: dict):
        builder = ApplicationBuilder()
        builder = builder.with_actions(
            precheck=PrecheckAction(self.retrieval_precheck, self.settings),
            gate=GateAction(self.gate, self.settings, self.mcp_manager),
            rewrite=RewriteAction(self.rewriter),
            retrieve=RetrieveAction(self.rrf_retriever, self.web_search, self.settings, self.mcp_manager),
            synthesize=SynthesizeAction(self.rag_synthesis, self.settings, self.mcp_manager),
            generic=GenericAction(self.generic_agent),
            decision=DecisionAction(self.decision_agent),
        )

        threshold = (
            initial_state["project_ctx"].confidence_threshold
            if initial_state.get("project_ctx")
            else self.settings.v2_confidence_threshold
        )

        builder = builder.with_transitions(
            ("precheck", "gate", default),
            ("gate", "generic", expr("route == 'generic'")),
            ("gate", "rewrite", expr("route in ['rag', 'web', 'hybrid']")),
            ("rewrite", "retrieve", default),
            ("retrieve", "synthesize", default),
            ("synthesize", "decision", default),
            ("generic", "decision", default),
            # Decision transitions: retry if verdict is not good or confidence is low, and attempts remaining
            (
                "decision",
                "rewrite",
                expr(
                    f"(verdict != 'good' or confidence < {threshold}) and attempt <= max_attempts"
                ),
            ),
        )
        builder = builder.with_entrypoint("precheck")
        builder = builder.with_state(**initial_state)
        # Register OpenTelemetryBridge hook
        try:
            from burr.integrations.opentelemetry import OpenTelemetryBridge
            builder = builder.with_hooks(OpenTelemetryBridge())
        except Exception as e:
            logger.warning("Failed to initialize OpenTelemetryBridge: %s", e)
        return builder.build()

    @traceable(name="BurrOrchestrator.search_stream", run_type="chain")
    def search_stream(
        self,
        query: str,
        *,
        project_ctx: ProjectContext | None = None,
        modality_filter: FileModality | None = None,
        conversation: ConversationState | None = None,
        web_search_mode: str = "auto",
        client_requested_tool: str | None = None,
        conversation_id: UUID | None = None,
        has_corpus: bool = True,
        use_cloud_llm: bool = False,
    ) -> Generator[str, None, None]:
        def emit(event: str, data: dict):
            payload = json.dumps({"event": event, "data": data}, default=str)
            return f"data: {payload}\n\n"

        stripped = query.strip()
        conv_state, conversation_context = self.conversation_memory.prepare(conversation)

        run_id = self.db_logger.start_run(
            query=stripped,
            modality_filter=modality_filter,
            conversation_context=conversation_context,
        )

        max_attempts = (
            project_ctx.max_attempts
            if project_ctx
            else max(1, self.settings.v2_max_pipeline_attempts)
        )
        project_id = project_ctx.project_id if project_ctx else UUID(int=0)

        initial_state = {
            "query": stripped,
            "conversation_context": conversation_context,
            "client_requested_tool": client_requested_tool,
            "has_corpus": has_corpus,
            "use_cloud_llm": use_cloud_llm,
            "route": None,
            "gate_result": None,
            "rewritten_query": stripped,
            "sources": [],
            "answer": "",
            "verdict": "good",
            "confidence": 1.0,
            "attempt": 1,
            "max_attempts": max_attempts,
            "prev_feedback": None,
            "project_ctx": project_ctx,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "modality_filter": modality_filter,
            "llm_calls": 0,
            "web_searches": 0,
            "tools": 0,
            "input_tokens": 0,
        }

        app = self.build_application(initial_state)

        # Execute step-by-step
        while True:
            # Enforce budget limits
            budget = RunBudget(
                attempts=app.state.get("attempt", 0),
                llm_calls=app.state.get("llm_calls", 0),
                web_searches=app.state.get("web_searches", 0),
                tools=app.state.get("tools", 0),
                input_tokens=app.state.get("input_tokens", 0),
            )
            budget.check()

            action_name = app.get_next_action().name

            # Yield BEFORE running the action to keep frontend status aligned
            if action_name == "precheck":
                yield emit(
                    "status", {"step": "precheck", "message": "Running retrieval pre-check..."}
                )
            elif action_name == "gate":
                gate_model = (
                    project_ctx.gate_model if project_ctx else self.settings.local_llm_gate_model
                )
                yield emit(
                    "status",
                    {"step": "gate", "model": gate_model, "message": "Classifying query route..."},
                )
            elif action_name == "rewrite":
                rewriter_model = (
                    project_ctx.rewriter_model
                    if project_ctx
                    else self.settings.local_llm_rewriter_model
                )
                attempt_num = app.state.get("attempt", 1)
                yield emit(
                    "status",
                    {
                        "step": "rewrite",
                        "model": rewriter_model,
                        "message": f"Rewriting search query (attempt {attempt_num}/{max_attempts})...",
                    },
                )
            elif action_name == "retrieve":
                yield emit(
                    "status",
                    {"step": "retrieve", "message": "Retrieving context from indexed sources..."},
                )
            elif action_name == "synthesize":
                synthesis_model = (
                    project_ctx.synthesis_model
                    if project_ctx
                    else self.settings.local_llm_rewriter_model
                )
                yield emit(
                    "status",
                    {
                        "step": "synthesis",
                        "model": synthesis_model,
                        "message": "Synthesizing answer...",
                    },
                )
            elif action_name == "generic":
                gate_model = (
                    project_ctx.gate_model if project_ctx else self.settings.local_llm_gate_model
                )
                yield emit(
                    "status",
                    {"step": "synthesis", "model": gate_model, "message": "Generating reply..."},
                )
            elif action_name == "decision":
                decision_model = (
                    project_ctx.decision_model
                    if project_ctx
                    else self.settings.local_llm_decision_model
                )
                yield emit(
                    "status",
                    {
                        "step": "decision",
                        "model": decision_model,
                        "message": "Evaluating generated answer content...",
                    },
                )

            # We execute the action
            def chunk_callback(chunk: str):
                # Helper thread-safe queue could be used, but standard direct yield works for single thread
                # Since app.step runs synchronously, callbacks will be executed in this thread synchronously
                nonlocal chunks_yielded
                chunks_yielded.append(chunk)

            chunks_yielded = []
            action, result, state = app.step(
                inputs={"web_search_mode": web_search_mode, "on_chunk": chunk_callback}
            )

            # Yield chunks collected during LLM step
            for chunk in chunks_yielded:
                yield emit("chunk", {"text": chunk})

            # Yield status updates AFTER running
            if action.name == "gate":
                gate_res = state.get("gate_result")
                self.db_logger.log_gate(run_id=run_id, gate_result=gate_res)
                yield emit(
                    "status",
                    {
                        "step": "gate_end",
                        "route": gate_res.route,
                        "message": f"Route decided: {gate_res.route.upper()}",
                    },
                )
            elif action.name == "rewrite":
                rewritten_text = state.get("rewritten_query")
                yield emit(
                    "status",
                    {
                        "step": "rewrite_end",
                        "rewritten": rewritten_text,
                        "message": f'Search terms optimized: "{rewritten_text}"',
                    },
                )
            elif action.name == "retrieve":
                sources = state.get("sources")
                yield emit(
                    "status",
                    {
                        "step": "retrieval_end",
                        "sources_count": len(sources),
                        "sources": [s.model_dump(mode="json") for s in sources],
                        "message": f"Found {len(sources)} relevant document matches.",
                    },
                )
            elif action.name == "synthesize":
                self.db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=state.get("attempt", 1) - 1,
                    synthesis_result=RagSynthesisResult(answer=state.get("answer"), llm_call=None),
                )
            elif action.name == "generic":
                self.db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=1,
                    synthesis_result=GenericReplyResult(answer=state.get("answer"), llm_call=None),
                )
            elif action.name == "decision":
                # Check evaluation result
                verdict = state.get("verdict")
                confidence = state.get("confidence")
                correct_route = state.get("route")
                feedback = state.get("prev_feedback")

                yield emit(
                    "status",
                    {
                        "step": "evaluation_end",
                        "confidence": confidence,
                        "verdict": verdict,
                        "correct_route": correct_route,
                        "message": f"Answer verified: {verdict.upper()} (Confidence: {int((confidence or 0)*100)}%)",
                    },
                )

                threshold = (
                    project_ctx.confidence_threshold
                    if project_ctx
                    else self.settings.v2_confidence_threshold
                )
                if confidence >= threshold and verdict == "good":
                    # Good answer, we exit
                    final_answer = state.get("answer")
                    updated_conversation = self.conversation_memory.record_exchange(
                        conv_state, stripped, final_answer
                    )
                    response = self._build_response(
                        query=stripped,
                        rewritten_query=state.get("rewritten_query"),
                        gate_result=state.get("gate_result"),
                        modality_filter=modality_filter,
                        answer=final_answer,
                        sources=state.get("sources"),
                        attempts=state.get("attempt", 1) - 1,
                        confidence=confidence,
                        disclaimer_appended=False,
                        conversation=updated_conversation,
                    )
                    self.db_logger.end_run(
                        run_id=run_id,
                        final_route=response.route,
                        final_answer=response.answer,
                        final_confidence=response.confidence,
                        attempts_count=response.attempts,
                        disclaimer_appended=response.disclaimer_appended,
                    )
                    yield emit("result", response.model_dump(mode="json"))
                    break

                if state.get("attempt", 1) <= max_attempts:
                    yield emit(
                        "status",
                        {
                            "step": "retry",
                            "feedback": feedback,
                            "message": f"Confidence below threshold. Retrying with feedback: {feedback}",
                        },
                    )
                else:
                    # Final attempt done, append low confidence disclaimer and return
                    final_answer = state.get("answer")
                    if LOW_CONFIDENCE_DISCLAIMER not in final_answer:
                        final_answer = f"{final_answer.rstrip()}\n\n{LOW_CONFIDENCE_DISCLAIMER}"
                    updated_conversation = self.conversation_memory.record_exchange(
                        conv_state, stripped, final_answer
                    )
                    response = self._build_response(
                        query=stripped,
                        rewritten_query=state.get("rewritten_query"),
                        gate_result=state.get("gate_result"),
                        modality_filter=modality_filter,
                        answer=final_answer,
                        sources=state.get("sources"),
                        attempts=max_attempts,
                        confidence=confidence,
                        disclaimer_appended=True,
                        conversation=updated_conversation,
                    )
                    self.db_logger.end_run(
                        run_id=run_id,
                        final_route=response.route,
                        final_answer=response.answer,
                        final_confidence=response.confidence,
                        attempts_count=response.attempts,
                        disclaimer_appended=response.disclaimer_appended,
                    )
                    yield emit("result", response.model_dump(mode="json"))
                    break

            if app.is_terminal():
                break

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
