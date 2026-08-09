import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, Callable, Generator, Literal
from uuid import UUID

from burr.core import ApplicationBuilder, State, default, expr
from burr.core.action import SingleStepAction
from langsmith import traceable

from app.core.config import Settings
from app.services.v4.run_budget import RunBudget, BudgetExceededError
from app.services.v5.cost_model import estimate_cost
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
from app.services.v4.evidence_assessor import EvidenceAssessor, InsufficientEvidenceError
from app.services.v4.citation_verifier import CitationVerifier
from app.services.v4.groundedness_evaluator import GroundednessEvaluator
from app.services.v4.memory_manager import MemoryManager
from sqlmodel import select
from app.models.tool_approval import ToolApproval
from app.tools.policy import PermissionChecker
from app.tools.execution_sandbox import execute_python_in_sandbox
from app.models.conversation import ChatConversation
from app.models.user import ProjectMember

logger = logging.getLogger(__name__)

NO_INDEXED_CONTENT = "No matching indexed content found."
LOW_CONFIDENCE_DISCLAIMER = "Note: answer may vary — retrieval confidence was low."
PDF_TITLE_FALLBACK = "generated-document"
PDF_TOOL_NAME = "generate_pdf"
FLOWCHART_TOOL_NAME = "generate_flowchart"
WEB_SEARCH_TOOL_NAME = "web_search"
TOOLS_REQUIRING_RAG = frozenset({PDF_TOOL_NAME, FLOWCHART_TOOL_NAME})

# Binary only — there is no "auto" mode. The toggle in the UI is either off (never,
# the default) or on (always); nothing in this pipeline should reintroduce a
# score-based/ambiguous middle mode.
WebSearchMode = Literal["always", "never"]


def web_search_allowed(web_search_mode: WebSearchMode) -> bool:
    """Single source of truth for 'is the model permitted to touch the web at all'."""
    return web_search_mode != "never"


def build_tool_context(
    *, mcp_enabled: bool, enable_web_search: bool, web_search_mode: WebSearchMode
) -> str:
    """Advertise tools to the gate LLM — but only the ones it is actually allowed to use.

    A model cannot request a tool it has never been told about. Listing `web_search`
    while the user has web search set to "never" is what made the gate keep choosing
    web/hybrid routes and setting requested_tool="web_search"; the route clamp then
    rewrote the route but the tool request (and the model's whole framing of the
    answer) survived. So the tool list is built per-turn from the user's preference
    rather than being a static capability dump.
    """
    tools: list[str] = []
    if mcp_enabled:
        tools.append(
            "- generate_pdf: Create a downloadable PDF document from synthesized "
            "project content."
        )
        tools.append(
            "- generate_flowchart: Generate a Mermaid flowchart diagram visualizing "
            "processes/workflows."
        )
    if enable_web_search and web_search_allowed(web_search_mode):
        tools.append(
            "- web_search: Search the web for real-time technology/AI news, startup "
            "funding, or recent tech developments."
        )
    return "\n".join(tools)


def build_gate_policy_directive(web_search_mode: WebSearchMode) -> str:
    """Hard routing policy injected into the gate system prompt at request time.

    The base gate prompt is static and unconditionally teaches the model to route
    real-time questions to "web"/"hybrid". Under an explicit user preference that
    instruction is wrong, so it gets overridden here instead of being silently
    contradicted after the fact by the route clamp.
    """
    if web_search_mode == "never":
        return (
            "MANDATORY ROUTING POLICY — OVERRIDES EVERY RULE ABOVE:\n"
            "The user has DISABLED web search for this request. Live internet access "
            "is unavailable to you.\n"
            "- You MUST NOT return route \"web\" or route \"hybrid\". They are forbidden.\n"
            "- The only permitted routes are \"rag\" and \"generic\".\n"
            "- You MUST NOT set requested_tool to \"web_search\".\n"
            "- If the question needs real-time information, still choose \"rag\" and "
            "answer from local documents only. Do not promise or imply a web lookup."
        )
    if web_search_mode == "always":
        return (
            "MANDATORY ROUTING POLICY — OVERRIDES EVERY RULE ABOVE:\n"
            "The user has FORCED web search on for this request. Every answer must be "
            "backed by a live web lookup.\n"
            "- You MUST NOT return route \"generic\" or route \"rag\". They are forbidden.\n"
            "- The only permitted routes are \"web\" and \"hybrid\".\n"
            "- Choose \"hybrid\" when local project documents are also relevant, "
            "otherwise \"web\".\n"
            "- Never answer conversationally instead of routing; a web search must happen."
        )
    return ""


def build_synthesis_policy_directive(web_search_mode: WebSearchMode) -> str:
    """Answer-time policy for the synthesis model (which also has tool-calling access)."""
    if web_search_mode == "never":
        return (
            "MANDATORY POLICY — OVERRIDES EVERY RULE ABOVE:\n"
            "Web search is DISABLED for this request. You have no internet access.\n"
            "- You MUST NOT call the web_search tool under any circumstance.\n"
            "- Answer strictly from the provided sources and the conversation.\n"
            "- If the sources do not cover the question, say so plainly instead of "
            "suggesting or pretending to look it up online."
        )
    if web_search_mode == "always":
        return (
            "POLICY: Web search is enabled and live web results are already included "
            "in the provided sources. Ground the answer in them and cite them."
        )
    return ""


def normalize_source_citations(answer: str, sources: list) -> str:
    """Normalize bracketed source tags like [Source 1] or [Source 1, Source 2] to [post_1105.txt]."""
    if not answer or not sources:
        return answer

    def _replace_source_match(match: re.Match) -> str:
        content = match.group(1)
        source_nums = re.findall(r"(?:Source|source)\s*(\d+)", content)
        if not source_nums:
            return match.group(0)

        replaced_citations = []
        for num_str in source_nums:
            idx = int(num_str) - 1
            if 0 <= idx < len(sources):
                title = getattr(sources[idx], "title", f"Source {num_str}")
                replaced_citations.append(f"[{title}]")
            else:
                replaced_citations.append(f"[Source {num_str}]")
        return " ".join(replaced_citations)

    normalized = re.sub(
        r"\[((?:Source|source)\s*\d+(?:\s*,\s*(?:Source|source)\s*\d+)*)\]",
        _replace_source_match,
        answer,
    )
    return normalized


def filter_tools_for_web_search_mode(
    tools: list[dict] | None, web_search_mode: WebSearchMode
) -> list[dict] | None:
    """Strip web_search from the synthesis tool schema list when the user forbade it.

    The synthesis model is handed the raw MCP tool list, which contains web_search.
    Prompt text alone is not a guarantee, so the capability is removed outright.
    """
    if not tools or web_search_allowed(web_search_mode):
        return tools
    filtered = [
        tool
        for tool in tools
        if (tool.get("function", {}).get("name") or tool.get("name"))
        != WEB_SEARCH_TOOL_NAME
    ]
    return filtered or None


def sanitize_requested_tool(
    requested_tool: str | None, web_search_mode: WebSearchMode
) -> str | None:
    if requested_tool == WEB_SEARCH_TOOL_NAME and not web_search_allowed(web_search_mode):
        return None
    return requested_tool


def count_tokens_fallback(text: str, model_name: str) -> int:
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


def constrain_route_for_web_search_mode(route: str, web_search_mode: WebSearchMode) -> str:
    """Clamp a route to what the user's web search preference actually allows.

    The user's choice is a hard constraint, not a hint any one step can override:
    "never" forbids web/hybrid outright, "always" guarantees a web component.
    Every place that can (re)assign `route` — the initial gate decision AND the
    decision/evaluator's retry suggestion — must call this, or a later step can
    silently reintroduce a path the user explicitly excluded.
    """
    if web_search_mode == "always":
        if route == "rag":
            return "hybrid"
        if route == "generic":
            return "web"
        return route
    if web_search_mode == "never":
        if route in ("web", "hybrid"):
            return "rag"
        return route
    return route


class PrecheckAction(SingleStepAction):
    def __init__(self, precheck: RetrievalPrecheck | None, settings: Settings):
        super().__init__()
        self.precheck = precheck
        self.settings = settings

    @property
    def reads(self) -> list[str]:
        return ["query", "project_id", "conversation_id", "has_corpus", "client_requested_tool", "conversation_context"]

    @property
    def writes(self) -> list[str]:
        return ["route", "precheck_action", "precheck_reason"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        if self.precheck is None:
            return {"action": "continue"}, state.update(
                precheck_action="continue", precheck_reason=None
            )

        web_search_mode = inputs.get("web_search_mode", "never")

        precheck_res = self.precheck.evaluate(
            state["query"],
            project_id=state["project_id"],
            conversation_id=state["conversation_id"],
            has_corpus=state["has_corpus"],
            client_requested_tool=state["client_requested_tool"],
            # The user's "never" preference is folded in here rather than being undone
            # downstream: without it the precheck happily returns route_web (e.g. for an
            # empty corpus), which the clamp then has to rewrite to rag.
            enable_web_search=(
                self.settings.enable_web_search and web_search_allowed(web_search_mode)
            ),
            conversation_context=state.get("conversation_context") or "",
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
            "cost_usd",
        ]

    @property
    def writes(self) -> list[str]:
        return ["route", "gate_result", "llm_calls", "input_tokens", "cost_usd"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        web_search_mode = inputs.get("web_search_mode", "never")

        # If precheck already determined the route, we skip gate classification — but
        # web_search_mode ("always"/"never") must still be enforced on this path. It
        # used to only be applied below, after an LLM gate call, so any query the cheap
        # precheck resolved on its own (the common case: confident retrieval score, or
        # no indexed corpus) silently ignored the user's web search preference entirely.
        if state["route"] is not None:
            gate_res = GateResult(
                route=state["route"],
                reason=state["precheck_reason"] or "Retrieval pre-check forced route.",
                requested_tool=state["client_requested_tool"],
                reply=None,
            )
            gate_res = self._apply_web_search_mode(gate_res, web_search_mode)
            return {"route": gate_res.route}, state.update(route=gate_res.route, gate_result=gate_res)

        project_ctx = state["project_ctx"]

        # Tool advertisement and routing policy are both rebuilt per request from the
        # user's web search preference — the model is never told about a capability it
        # is not allowed to use, and is explicitly forced when the user demands web.
        tool_context = build_tool_context(
            mcp_enabled=bool(self.mcp_manager and self.mcp_manager.is_enabled()),
            enable_web_search=self.settings.enable_web_search,
            web_search_mode=web_search_mode,
        )
        policy_directive = build_gate_policy_directive(web_search_mode)

        # Estimate input tokens before calling LLM
        prompt_len = (
            len(state["query"])
            + len(tool_context)
            + len(policy_directive)
            + len(state["conversation_context"])
        )

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
            policy_directive=policy_directive,
        )

        # Apply web search mode overrides if any
        gate_res = self._apply_web_search_mode(gate_res, web_search_mode)

        return self._finalize(state, gate_res, prompt_len, web_search_mode)

    @staticmethod
    def _apply_web_search_mode(gate_res: GateResult, web_search_mode: WebSearchMode) -> GateResult:
        new_route = constrain_route_for_web_search_mode(gate_res.route, web_search_mode)
        # The tool request is clamped alongside the route. Clamping only the route left
        # requested_tool="web_search" alive under "never", which then reached synthesis
        # and got executed there.
        new_tool = sanitize_requested_tool(gate_res.requested_tool, web_search_mode)
        if new_route == gate_res.route and new_tool == gate_res.requested_tool:
            return gate_res
        return GateResult(
            route=new_route,
            reason=f"{gate_res.reason} (Web search mode: {web_search_mode.upper()})",
            reply=None if new_route != "generic" else gate_res.reply,
            requested_tool=new_tool,
        )

    def _finalize(
        self,
        state: State,
        gate_res: GateResult,
        prompt_len: int = 0,
        web_search_mode: WebSearchMode = "never",
    ) -> tuple[dict, State]:
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
            # Forcing "rag" here happens *after* the web search mode clamp, so without
            # re-clamping, asking for a PDF with web search set to "always" silently
            # dropped the web half of the request. Re-clamp so both constraints hold:
            # "always" lands on hybrid (retrieval + web, then the document).
            gate_res = self._apply_web_search_mode(gate_res, web_search_mode)

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        cost_usd = state.get("cost_usd", 0.0)

        if gate_res.llm_call:
            llm_calls += 1
            input_tokens += gate_res.llm_call.prompt_tokens
            cost_usd += float(estimate_cost(gate_res.llm_call.model_name, {
                "prompt_tokens": gate_res.llm_call.prompt_tokens,
                "completion_tokens": gate_res.llm_call.completion_tokens,
                "cached_tokens": gate_res.llm_call.cached_tokens,
            }))
        else:
            if state["route"] is None:
                llm_calls += 1
                input_tokens += (prompt_len // 4 + 200)

        return {"route": gate_res.route}, state.update(
            route=gate_res.route,
            gate_result=gate_res,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
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
            "cost_usd",
        ]

    @property
    def writes(self) -> list[str]:
        return ["rewritten_query", "rewrite_result", "llm_calls", "input_tokens", "cost_usd"]

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

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        cost_usd = state.get("cost_usd", 0.0)

        if rewritten.llm_call:
            llm_calls += 1
            input_tokens += rewritten.llm_call.prompt_tokens
            cost_usd += float(estimate_cost(rewritten.llm_call.model_name, {
                "prompt_tokens": rewritten.llm_call.prompt_tokens,
                "completion_tokens": rewritten.llm_call.completion_tokens,
                "cached_tokens": rewritten.llm_call.cached_tokens,
            }))
        else:
            llm_calls += 1
            prompt_len = len(state["query"]) + len(state["conversation_context"]) + len(state["prev_feedback"] or "")
            input_tokens += (prompt_len // 4 + 300)

        return {"rewritten_query": rewritten.text}, state.update(
            rewritten_query=rewritten.text,
            rewrite_result=rewritten,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
        )


class RetrieveAction(SingleStepAction):
    def __init__(
        self,
        rrf_retriever: RrfRetriever,
        web_search: WebSearchService | None,
        settings: Settings,
        mcp_manager: McpClientManager | None,
        memory_manager: MemoryManager | None = None,
    ):
        super().__init__()
        self.rrf = rrf_retriever
        self.web_search = web_search
        self.settings = settings
        self.mcp_manager = mcp_manager
        self.memory_manager = memory_manager

    @property
    def reads(self) -> list[str]:
        return [
            "rewritten_query",
            "project_id",
            "modality_filter",
            "route",
            "conversation_id",
            "web_searches",
            "cost_usd",
            "gate_result",
        ]

    @property
    def writes(self) -> list[str]:
        return ["sources", "web_searches", "cost_usd", "retrieval_stats", "source_rank_fields", "retrieval_candidates", "retrieval_candidate_rank_fields", "retrieval_prompt_tokens", "retrieval_cost_usd", "route", "gate_result"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        rewritten_text = state["rewritten_query"]
        project_id = state["project_id"]
        modality_filter = state["modality_filter"]
        route = state["route"]
        conversation_id = state["conversation_id"]
        web_search_mode = inputs.get("web_search_mode", "never")

        disable_web = not web_search_allowed(web_search_mode)
        force_web = web_search_mode == "always"
        web_searches = state.get("web_searches", 0)
        cost_usd = state.get("cost_usd", 0.0)

        # Last line of defence for "always": whatever the gate, the tool forcing, or a
        # decision-agent retry decided upstream, a run the user marked "always" does not
        # reach synthesis without live web results. Treating a leftover "rag" as hybrid
        # here means no future routing change can quietly drop the web half again.
        gate_result = state.get("gate_result")
        if force_web and route == "rag":
            logger.info("web_search_mode=always: upgrading leftover rag route to hybrid.")
            route = "hybrid"
            # Keep gate_result in sync — it is what the final response and the pipeline
            # logs report as "route", so leaving it on "rag" would show the user RAG
            # while web results were actually used.
            if gate_result is not None:
                gate_result = GateResult(
                    route="hybrid",
                    reason=f"{gate_result.reason} (Web search mode: ALWAYS)",
                    reply=None,
                    requested_tool=gate_result.requested_tool,
                )

        if route == "web":
            if disable_web:
                sources = []
            else:
                sources = self._retrieve_web(rewritten_text)
                web_searches += 1
            return {"sources": sources}, state.update(
                sources=sources,
                web_searches=web_searches,
                retrieval_stats=None,
                source_rank_fields=None,
                retrieval_candidates=None,
                retrieval_candidate_rank_fields=None,
                retrieval_prompt_tokens=0,
                retrieval_cost_usd=0.0,
            )

        # Run RRF retrieval
        retrieval = self.rrf.retrieve(
            rewritten_text,
            project_id=project_id,
            modality_filter=modality_filter,
            conversation_id=conversation_id,
            include_project_wide=True,
        )
        sources = retrieval.sources
        source_rank_fields = retrieval.source_rank_fields
        retrieval_candidates = retrieval.candidates
        retrieval_candidate_rank_fields = retrieval.candidate_rank_fields

        if route == "hybrid" and not disable_web:
            web_sources = self._retrieve_web(rewritten_text)
            sources = sources + web_sources
            web_searches += 1
        elif not sources and self.settings.enable_web_search and not disable_web:
            web_sources = self._retrieve_web(rewritten_text)
            sources = web_sources
            web_searches += 1

        # Run Graphiti retrieval if memory manager is available and route uses documents
        if self.memory_manager and project_id and route in ("rag", "hybrid"):
            try:
                graph_sources = self.memory_manager.query_temporal_graph(project_id, rewritten_text)
                sources = sources + graph_sources
            except Exception as e:
                logger.warning("Failed to query Graphiti temporal graph: %s", e)

        # Rerank combined results to put the best on top
        sources.sort(key=lambda s: s.score, reverse=True)

        # Calculate embedding cost
        embedding_cost = 0.0
        num_tokens = 0
        if route in ("rag", "hybrid"):
            try:
                num_tokens = count_tokens_fallback(rewritten_text, self.settings.embedding_model)
            except Exception:
                num_tokens = len(rewritten_text) // 4
            
            embedding_cost = float(estimate_cost(self.settings.embedding_model, {
                "prompt_tokens": num_tokens,
                "completion_tokens": 0,
                "cached_tokens": 0,
            }))
            cost_usd += embedding_cost

        return {"sources": sources}, state.update(
            sources=sources,
            route=route,
            gate_result=gate_result,
            web_searches=web_searches,
            cost_usd=cost_usd,
            retrieval_stats=retrieval.stats,
            source_rank_fields=source_rank_fields,
            retrieval_candidates=retrieval_candidates,
            retrieval_candidate_rank_fields=retrieval_candidate_rank_fields,
            retrieval_prompt_tokens=num_tokens,
            retrieval_cost_usd=embedding_cost,
        )

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
        session: Any = None,
    ):
        super().__init__()
        self.rag_synthesis = rag_synthesis
        self.settings = settings
        self.mcp_manager = mcp_manager
        self.session = session

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
            "conversation_id",
            "project_id",
            "cost_usd",
            "client_requested_tool",
            "attempt",
            "prev_feedback",
            "retry_target",
        ]

    @property
    def writes(self) -> list[str]:
        return ["answer", "llm_calls", "input_tokens", "tools", "cost_usd", "synthesis_result"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        query = state["query"]
        rewritten_text = state["rewritten_query"]
        sources = state["sources"]
        gate_result = state["gate_result"]
        conversation_context = state["conversation_context"]
        project_ctx = state["project_ctx"]
        on_chunk = inputs.get("on_chunk")
        web_search_mode = inputs.get("web_search_mode", "never")
        policy_directive = build_synthesis_policy_directive(web_search_mode)

        # Synthesis-only retry (citation/groundedness failure, sources unchanged):
        # fold the verifier's feedback into the prompt so regeneration actually
        # addresses it, since we're skipping the rewrite step that would
        # normally carry prev_feedback into a fresh query.
        if state.get("retry_target") == "synthesize" and state.get("attempt", 1) > 1 and state.get("prev_feedback"):
            rewritten_text = f"{rewritten_text}\n\n[Regeneration instruction: {state['prev_feedback']}]"

        pdf_requested = gate_result.requested_tool == PDF_TOOL_NAME
        flowchart_requested = gate_result.requested_tool == FLOWCHART_TOOL_NAME

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        tools_count = state.get("tools", 0)
        cost_usd = state.get("cost_usd", 0.0)

        if not sources:
            if pdf_requested:
                gen_res = self._draft_document_content(
                    rewritten_text, conversation_context, project_ctx, policy_directive
                )
                answer = gen_res.answer
                llm_call = gen_res.llm_call
                if llm_call:
                    llm_calls += 1
                    input_tokens += llm_call.prompt_tokens
                    cost_usd += float(estimate_cost(llm_call.model_name, {
                        "prompt_tokens": llm_call.prompt_tokens,
                        "completion_tokens": llm_call.completion_tokens,
                        "cached_tokens": llm_call.cached_tokens,
                    }))
                answer = self._attach_pdf_to_answer(query, answer)
                tools_count += 1
                synthesis_result = gen_res
            elif flowchart_requested:
                gen_res = self._draft_document_content(
                    rewritten_text, conversation_context, project_ctx, policy_directive
                )
                answer = gen_res.answer
                llm_call = gen_res.llm_call
                if llm_call:
                    llm_calls += 1
                    input_tokens += llm_call.prompt_tokens
                    cost_usd += float(estimate_cost(llm_call.model_name, {
                        "prompt_tokens": llm_call.prompt_tokens,
                        "completion_tokens": llm_call.completion_tokens,
                        "cached_tokens": llm_call.cached_tokens,
                    }))
                answer = self._attach_flowchart_to_answer(query, answer)
                tools_count += 1
                synthesis_result = gen_res
            else:
                answer = NO_INDEXED_CONTENT
                synthesis_result = RagSynthesisResult(answer=answer, llm_call=None)

            if on_chunk:
                on_chunk(answer)

            return {"answer": answer}, state.update(
                answer=answer,
                llm_calls=llm_calls,
                input_tokens=input_tokens,
                cost_usd=cost_usd,
                tools=tools_count,
                synthesis_result=synthesis_result,
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
        # The MCP tool list contains web_search. Handing it to the synthesis model on a
        # "never" run let the model perform a web search after routing had already been
        # constrained — the single biggest way the toggle was being ignored. Remove the
        # capability rather than relying on the prompt to discourage it.
        tools = filter_tools_for_web_search_mode(tools, web_search_mode)

        sources_len = sum(len(s.content) for s in sources)
        prompt_length = len(rewritten_text) + sources_len + len(conversation_context)

        if tools or pdf_requested or flowchart_requested:
            # Run blocking synthesis to allow tool calling
            synthesis_result = self.rag_synthesis.synthesize(
                rewritten_text,
                sources,
                model=project_ctx.synthesis_model if project_ctx else None,
                system_override=(
                    project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                ),
                conversation_context=conversation_context,
                tools=tools,
                policy_directive=policy_directive,
            )
            answer = synthesis_result.answer
            llm_call = synthesis_result.llm_call
            
            if llm_call:
                llm_calls += 1
                input_tokens += llm_call.prompt_tokens
                cost_usd += float(estimate_cost(llm_call.model_name, {
                    "prompt_tokens": llm_call.prompt_tokens,
                    "completion_tokens": llm_call.completion_tokens,
                    "cached_tokens": llm_call.cached_tokens,
                }))

            tool_result = None

            if llm_call and llm_call.tool_calls:
                for tool_call in llm_call.tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.arguments

                    # Resolve user role for permission check
                    user_role = "member"
                    conversation_id = state.get("conversation_id")
                    project_id = state.get("project_id")

                    if self.session and conversation_id:
                        conv = self.session.get(ChatConversation, conversation_id)
                        if conv:
                            if not project_id or str(project_id) == "00000000-0000-0000-0000-000000000000":
                                user_role = "owner"
                            else:
                                user_id = conv.owner_user_id
                                member = self.session.exec(
                                    select(ProjectMember).where(
                                        ProjectMember.user_id == user_id,
                                        ProjectMember.project_id == project_id
                                    )
                                ).first()
                                if member:
                                    user_role = member.role

                    provenance = "model"
                    if (
                        state.get("client_requested_tool") == tool_name
                        or (state.get("gate_result") and state.get("gate_result").requested_tool == tool_name)
                    ):
                        provenance = "user"

                    # Check permission
                    if not PermissionChecker.check_permission(tool_name, user_role, provenance):
                        answer = f"Permission Denied: User role '{user_role}' is not authorized to execute tool '{tool_name}'."
                        break

                    # Check if human approval is required
                    if PermissionChecker.requires_approval(tool_name):
                        # Create a pending approval record
                        approval = ToolApproval(
                            conversation_id=conversation_id,
                            tool_name=tool_name,
                            arguments=tool_args,
                            status="waiting"
                        )
                        self.session.add(approval)
                        self.session.commit()
                        self.session.refresh(approval)

                        # Emit approval.required event
                        on_emit = inputs.get("on_emit")
                        if on_emit:
                            on_emit(
                                "approval.required",
                                {
                                    "approval_id": str(approval.id),
                                    "tool_name": tool_name,
                                    "arguments": tool_args,
                                }
                            )

                        # Block/Sleep-loop and refresh DB
                        import time
                        status = "waiting"
                        while status == "waiting":
                            time.sleep(1.0)
                            self.session.commit()
                            approval_db = self.session.exec(
                                select(ToolApproval).where(ToolApproval.id == approval.id)
                            ).first()
                            if approval_db:
                                status = approval_db.status
                                approval = approval_db
                            else:
                                status = "rejected"

                        if status == "rejected":
                            answer = f"Execution rejected by user for tool '{tool_name}'."
                            break

                    if tool_name == "generate_pdf":
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
                    elif tool_name == "generate_flowchart":
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
                    elif tool_name == "execute_python":
                        try:
                            sandbox_output = self.mcp_manager.call_tool(
                                tool_name, tool_call.arguments
                            )
                            answer = f"{synthesis_result.answer.strip()}\n\nSandbox execution output:\n```\n{sandbox_output}\n```"
                            tool_result = sandbox_output
                            tools_count += 1
                        except Exception as e:
                            answer = f"Sandbox execution failed: {e}"
                        break
                    elif tool_name == "web_search":
                        # Defence in depth: the schema was already withheld above, so a
                        # call here means the model invented the tool. Refuse it rather
                        # than executing a search the user switched off.
                        if not web_search_allowed(web_search_mode):
                            logger.warning(
                                "Blocked web_search tool call: web_search_mode=%s.",
                                web_search_mode,
                            )
                            break
                        try:
                            results = self.mcp_manager.call_tool(
                                tool_name, tool_call.arguments
                            )
                            answer = f"{synthesis_result.answer.strip()}\n\nSearch Results:\n{results}"
                            tool_result = results
                            tools_count += 1
                        except Exception as e:
                            answer = f"Web search tool failed: {e}"
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
            answer = ""
            for chunk in self.rag_synthesis.synthesize_stream(
                rewritten_text,
                sources,
                model=project_ctx.synthesis_model if project_ctx else None,
                system_override=(
                    project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                ),
                conversation_context=conversation_context,
                policy_directive=policy_directive,
            ):
                answer += chunk
                if on_chunk:
                    on_chunk(chunk)
            
            evidence_res = state.get("evidence_assessment_result")
            is_sufficient = evidence_res.is_sufficient if evidence_res else True
            top_score = sources[0].score if sources else 0.0

            # Deterministic Refusal Recovery: If sources exist and evidence assessment confirmed sufficiency (or top score is high), but synthesis outputted abstention refusal string
            if sources and (is_sufficient or top_score >= 0.015) and "could not find sufficient information" in answer.strip().lower():
                logger.info("Deterministic refusal override triggered: retrieved %d sources but synthesis refused. Forcing summary generation.", len(sources))
                forced_directive = (
                    f"{policy_directive}\n\nCRITICAL MANDATORY INSTRUCTION: You MUST answer the user query using the provided retrieved sources. "
                    "Summarize the facts, articles, and details present in the sources to directly address the user's query. "
                    "Do NOT output 'I could not find sufficient information'."
                ).strip()
                answer = ""
                for chunk in self.rag_synthesis.synthesize_stream(
                    rewritten_text,
                    sources,
                    model=project_ctx.synthesis_model if project_ctx else None,
                    system_override=(
                        project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
                    ),
                    conversation_context=conversation_context,
                    policy_directive=forced_directive,
                ):
                    answer += chunk
                    if on_chunk:
                        on_chunk(chunk)

            # Normalize [Source 1] -> [post_1105.txt] filenames for consistent citation tracking
            answer = normalize_source_citations(answer, sources)
            
            # Estimate tokens
            model_name = project_ctx.synthesis_model if project_ctx else self.settings.local_llm_rewriter_model
            
            # Construct a helper prompt representation to estimate prompt tokens
            lines = []
            for index, source in enumerate(sources, start=1):
                lines.append(source.content)
            prompt_str = rewritten_text + "\n".join(lines) + conversation_context
            
            prompt_tokens_est = count_tokens_fallback(prompt_str, model_name)
            completion_tokens_est = count_tokens_fallback(answer, model_name)
            
            llm_calls += 1
            input_tokens += prompt_tokens_est
            cost_usd += float(estimate_cost(model_name, {
                "prompt_tokens": prompt_tokens_est,
                "completion_tokens": completion_tokens_est,
                "cached_tokens": 0,
            }))
            
            from app.services.v2.llm_clients.base import LlmResponse
            llm_call = LlmResponse(
                content=answer,
                model_name=model_name,
                prompt_system=project_ctx.system_prompt_overrides.get("synthesis") or "",
                prompt_user=rewritten_text,
                prompt_tokens=prompt_tokens_est,
                completion_tokens=completion_tokens_est,
                cached_tokens=0,
            )
            synthesis_result = RagSynthesisResult(answer=answer, llm_call=llm_call)

        return {"answer": answer}, state.update(
            answer=answer,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
            tools=tools_count,
            synthesis_result=synthesis_result,
        )

    def _draft_document_content(
        self,
        query: str,
        conversation_context: str,
        project_ctx: ProjectContext | None = None,
        policy_directive: str = "",
    ) -> RagSynthesisResult:
        generic_result = self.rag_synthesis.synthesize(
            query,
            [],
            model=project_ctx.synthesis_model if project_ctx else None,
            system_override=(
                project_ctx.system_prompt_overrides.get("synthesis") if project_ctx else None
            ),
            conversation_context=conversation_context,
            policy_directive=policy_directive,
        )
        return generic_result

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


class AssessEvidenceAction(SingleStepAction):
    def __init__(self, evidence_assessor: EvidenceAssessor | None):
        super().__init__()
        self.assessor = evidence_assessor

    @property
    def reads(self) -> list[str]:
        return ["query", "sources", "use_cloud_llm", "project_ctx", "llm_calls", "input_tokens", "cost_usd"]

    @property
    def writes(self) -> list[str]:
        return ["evidence_assessment", "llm_calls", "input_tokens", "cost_usd"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        if not self.assessor:
            from app.schemas.v4.rag import EvidenceAssessmentResult
            default_assessment = EvidenceAssessmentResult(is_sufficient=True, reasoning="No assessor configured", missing_information=None)
            return {"evidence_assessment": default_assessment}, state.update(evidence_assessment=default_assessment)

        project_ctx = state["project_ctx"]
        assessment = self.assessor.evaluate(
            query=state["query"],
            sources=state["sources"],
            use_cloud_llm=state["use_cloud_llm"],
            model=project_ctx.gate_model if project_ctx else None,
        )

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        cost_usd = state.get("cost_usd", 0.0)

        if assessment.llm_call:
            llm_calls += 1
            input_tokens += assessment.llm_call.prompt_tokens
            cost_usd += float(estimate_cost(assessment.llm_call.model_name, {
                "prompt_tokens": assessment.llm_call.prompt_tokens,
                "completion_tokens": assessment.llm_call.completion_tokens,
                "cached_tokens": assessment.llm_call.cached_tokens,
            }))

        if not assessment.is_sufficient:
            if assessment.missing_information:
                msg = (
                    "I couldn't find enough information in the project sources to answer this. "
                    f"Specifically missing: {assessment.missing_information}"
                )
            else:
                msg = "I could not find sufficient information in the provided sources."
            raise InsufficientEvidenceError(msg)

        return {"evidence_assessment": assessment}, state.update(
            evidence_assessment=assessment,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
        )


class VerifyAndEvaluateAction(SingleStepAction):
    """Runs citation verification and groundedness evaluation concurrently.

    Both stages take the same (query, answer, sources) input and are
    otherwise independent — running them in parallel threads instead of
    sequentially halves their combined wall-clock cost on every RAG turn.
    """

    def __init__(
        self,
        citation_verifier: CitationVerifier | None,
        groundedness_evaluator: GroundednessEvaluator | None,
    ):
        super().__init__()
        self.verifier = citation_verifier
        self.evaluator = groundedness_evaluator

    @property
    def reads(self) -> list[str]:
        return ["query", "answer", "sources", "use_cloud_llm", "project_ctx", "llm_calls", "input_tokens", "cost_usd"]

    @property
    def writes(self) -> list[str]:
        return ["citation_map_result", "groundedness_result", "llm_calls", "input_tokens", "cost_usd"]

    def _verify_citations(self, state: State) -> "CitationMapResult":
        if not self.verifier:
            from app.schemas.v4.rag import CitationMapResult
            return CitationMapResult(has_valid_citations=True, mappings=[])

        project_ctx = state["project_ctx"]
        return self.verifier.verify(
            query=state["query"],
            draft_answer=state["answer"],
            sources=state["sources"],
            use_cloud_llm=state["use_cloud_llm"],
            model=project_ctx.gate_model if project_ctx else None,
        )

    def _evaluate_groundedness(self, state: State) -> "GroundednessResult":
        if not self.evaluator:
            from app.schemas.v4.rag import GroundednessResult
            return GroundednessResult(score=1.0, reasoning="No evaluator configured", is_grounded=True)

        project_ctx = state["project_ctx"]
        return self.evaluator.evaluate(
            query=state["query"],
            answer=state["answer"],
            sources=state["sources"],
            use_cloud_llm=state["use_cloud_llm"],
            model=project_ctx.gate_model if project_ctx else None,
        )

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        with ThreadPoolExecutor(max_workers=2) as pool:
            citation_future = pool.submit(self._verify_citations, state)
            groundedness_future = pool.submit(self._evaluate_groundedness, state)
            citation_result = citation_future.result()
            groundedness_result = groundedness_future.result()

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        cost_usd = state.get("cost_usd", 0.0)

        for result in (citation_result, groundedness_result):
            if result.llm_call:
                llm_calls += 1
                input_tokens += result.llm_call.prompt_tokens
                cost_usd += float(estimate_cost(result.llm_call.model_name, {
                    "prompt_tokens": result.llm_call.prompt_tokens,
                    "completion_tokens": result.llm_call.completion_tokens,
                    "cached_tokens": result.llm_call.cached_tokens,
                }))

        return {
            "citation_map_result": citation_result,
            "groundedness_result": groundedness_result,
        }, state.update(
            citation_map_result=citation_result,
            groundedness_result=groundedness_result,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
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
            "citation_map_result",
            "groundedness_result",
            "cost_usd",
        ]

    @property
    def writes(self) -> list[str]:
        return ["verdict", "confidence", "attempt", "prev_feedback", "llm_calls", "input_tokens", "route", "cost_usd", "decision_result", "retry_target"]

    def run_and_update(self, state: State, **inputs) -> tuple[dict, State]:
        project_ctx = state["project_ctx"]

        if state["route"] == "generic":
            from app.services.v2.decision_agent import DecisionResult
            decision = DecisionResult(
                verdict="good",
                confidence=1.0,
                feedback="Generic conversational route bypasses validation.",
                correct_route="generic",
                llm_call=None
            )
            verdict = "good"
            confidence = 1.0
            feedback = decision.feedback
        else:
            # Default decision from standard DecisionAgent
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

            verdict = decision.verdict
            confidence = decision.confidence
            feedback = decision.feedback or "Improve query specificity and keywords."

        # Apply strict verification checks (Phase 2)
        citation_map = state.get("citation_map_result")
        groundedness = state.get("groundedness_result")

        # A verdict flip caused *only* by citation/groundedness failure means
        # retrieval and routing were fine — the draft just needs to be
        # regenerated against the same sources. Retrying from "rewrite" would
        # redo query rewriting + retrieval + evidence assessment for nothing,
        # so route that case straight back to "synthesize" instead.
        retry_target = "rewrite"
        if verdict == "good":
            if citation_map and not citation_map.has_valid_citations:
                verdict = "retry"
                confidence = 0.0
                feedback = "Fabricated or invalid citations detected. Please regenerate with valid source citations."
                retry_target = "synthesize"
            elif groundedness and not groundedness.is_grounded:
                verdict = "retry"
                confidence = groundedness.score
                feedback = f"Ungrounded claims detected (score {groundedness.score:.2f}). Please regenerate and stick strictly to the sources: {groundedness.reasoning}."
                retry_target = "synthesize"
        elif verdict == "retry" and decision and decision.feedback:
            # Preserve decision agent's feedback when decision agent triggered the retry
            feedback = decision.feedback
            if any(k in feedback.lower() for k in ("synthesize", "citation", "groundedness", "summarize")):
                retry_target = "synthesize"

        llm_calls = state.get("llm_calls", 0)
        input_tokens = state.get("input_tokens", 0)
        cost_usd = state.get("cost_usd", 0.0)

        if decision.llm_call:
            llm_calls += 1
            input_tokens += decision.llm_call.prompt_tokens
            cost_usd += float(estimate_cost(decision.llm_call.model_name, {
                "prompt_tokens": decision.llm_call.prompt_tokens,
                "completion_tokens": decision.llm_call.completion_tokens,
                "cached_tokens": decision.llm_call.cached_tokens,
            }))
        else:
            sources_len = sum(len(s.content) for s in state["sources"])
            prompt_len = len(state["query"]) + len(state["rewritten_query"]) + len(state["answer"]) + sources_len
            input_tokens += (prompt_len // 4 + 400)

        # The evaluator suggests a "correct route" for the retry with no awareness of
        # the user's web search preference — it must be clamped the same way the
        # initial gate decision is, or a retry can silently reintroduce (or drop) web
        # search against the user's explicit choice.
        web_search_mode = inputs.get("web_search_mode", "never")
        next_route = constrain_route_for_web_search_mode(
            decision.correct_route or state["route"], web_search_mode
        )

        # `decision` may still hold the DecisionAgent's raw, pre-override verdict (e.g.
        # "good"/1.0 when it judged the ROUTE as correct) even though the citation/
        # groundedness checks above just overrode verdict/confidence/feedback to force a
        # retry. Logging `decision` as-is would show a "good, confidence 1.0" evaluation
        # step right next to a failed citation/groundedness check with no visible link
        # between them — log the corrected values that actually drove the retry instead.
        logged_decision = replace(
            decision, verdict=verdict, confidence=confidence, feedback=feedback
        )

        return {
            "verdict": verdict,
            "confidence": confidence,
            "feedback": feedback,
            "correct_route": decision.correct_route,
            "retry_target": retry_target,
        }, state.update(
            verdict=verdict,
            confidence=confidence,
            attempt=state["attempt"] + 1,
            prev_feedback=feedback,
            route=next_route,
            decision_result=logged_decision,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            cost_usd=cost_usd,
            retry_target=retry_target,
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
        # New Phase 2 services
        memory_manager: MemoryManager | None = None,
        evidence_assessor: EvidenceAssessor | None = None,
        citation_verifier: CitationVerifier | None = None,
        groundedness_evaluator: GroundednessEvaluator | None = None,
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
        self.session = session
        self.db_logger = PipelineLogger(session)
        # New services (Phase 2)
        self.memory_manager = memory_manager
        self.evidence_assessor = evidence_assessor
        self.citation_verifier = citation_verifier
        self.groundedness_evaluator = groundedness_evaluator

    def build_application(self, initial_state: dict):
        builder = ApplicationBuilder()
        builder = builder.with_actions(
            precheck=PrecheckAction(self.retrieval_precheck, self.settings),
            gate=GateAction(self.gate, self.settings, self.mcp_manager),
            rewrite=RewriteAction(self.rewriter),
            retrieve=RetrieveAction(self.rrf_retriever, self.web_search, self.settings, self.mcp_manager, self.memory_manager),
            assess_evidence=AssessEvidenceAction(self.evidence_assessor),
            synthesize=SynthesizeAction(self.rag_synthesis, self.settings, self.mcp_manager, self.session),
            verify_and_evaluate=VerifyAndEvaluateAction(self.citation_verifier, self.groundedness_evaluator),
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
            ("retrieve", "assess_evidence", default),
            ("assess_evidence", "synthesize", default),
            ("synthesize", "verify_and_evaluate", default),
            ("verify_and_evaluate", "decision", default),
            ("generic", "decision", default),
            # Decision transitions: a citation/groundedness-only failure (retry_target
            # == 'synthesize') skips straight back to synthesis, reusing the existing
            # sources instead of redoing rewrite + retrieve + evidence assessment.
            (
                "decision",
                "synthesize",
                expr("retry_target == 'synthesize' and attempt <= max_attempts"),
            ),
            (
                "decision",
                "rewrite",
                expr(
                    f"retry_target == 'rewrite' and (verdict != 'good' or confidence < {threshold}) and attempt <= max_attempts"
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
        web_search_mode: WebSearchMode = "never",
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

        project_id = project_ctx.project_id if project_ctx else UUID(int=0)

        # Injects Letta persistent user memory (Phase 2)
        if self.memory_manager and project_id:
            try:
                letta_context = self.memory_manager.get_user_memory(project_id)
                if letta_context.strip():
                    conversation_context = f"{letta_context.strip()}\n\n{conversation_context}"
            except Exception as e:
                logger.warning("Failed to retrieve Letta context: %s", e)

        run_id = self.db_logger.start_run(
            query=stripped,
            modality_filter=modality_filter,
            conversation_context=conversation_context,
            project_id=project_id,
        )
        if run_id:
            yield emit("status", {"phase": "run_start", "step": "run_start", "run_id": str(run_id)})

        max_attempts = (
            project_ctx.max_attempts
            if project_ctx
            else max(1, self.settings.v2_max_pipeline_attempts)
        )

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
            "retry_target": "rewrite",
            "project_ctx": project_ctx,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "modality_filter": modality_filter,
            "llm_calls": 0,
            "web_searches": 0,
            "tools": 0,
            "input_tokens": 0,
            "cost_usd": 0.0,
            "evidence_assessment": None,
            "citation_map_result": None,
            "groundedness_result": None,
            "synthesis_result": None,
            "rewrite_result": None,
        }

        app = self.build_application(initial_state)

        # Execute step-by-step
        while True:
            # Enforce budget limits
            budget = RunBudget(
                max_attempts=self.settings.run_budget_max_attempts,
                max_llm_calls=self.settings.run_budget_max_llm_calls,
                max_web_searches=self.settings.run_budget_max_web_searches,
                max_tools=self.settings.run_budget_max_tools,
                max_input_tokens=self.settings.run_budget_max_input_tokens,
                max_cost_usd=self.settings.run_budget_max_cost_usd,
                attempts=app.state.get("attempt", 0),
                llm_calls=app.state.get("llm_calls", 0),
                web_searches=app.state.get("web_searches", 0),
                tools=app.state.get("tools", 0),
                input_tokens=app.state.get("input_tokens", 0),
                cost_usd=app.state.get("cost_usd", 0.0),
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
            elif action_name == "assess_evidence":
                yield emit(
                    "status",
                    {"step": "assess_evidence", "message": "Evaluating evidence sufficiency..."},
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
            elif action_name == "verify_and_evaluate":
                yield emit(
                    "status",
                    {
                        "step": "verify_and_evaluate",
                        "message": "Verifying citations and evaluating groundedness...",
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
            custom_events_yielded = []

            def emit_callback(event: str, data: dict):
                custom_events_yielded.append((event, data))

            action, result, state = app.step(
                inputs={
                    "web_search_mode": web_search_mode,
                    "on_chunk": chunk_callback,
                    "on_emit": emit_callback,
                }
            )

            # Yield custom events collected during step execution
            for event, data in custom_events_yielded:
                yield emit(event, data)

            # Yield chunks collected during LLM step
            for chunk in chunks_yielded:
                yield emit("chunk", {"text": chunk})

            # Yield status updates AFTER running
            # Yield status updates AFTER running
            if action.name == "precheck":
                precheck_action = state.get("precheck_action", "continue")
                precheck_reason = state.get("precheck_reason")
                route = state.get("route")
                self.db_logger.log_precheck(
                    run_id=run_id,
                    action=precheck_action,
                    reason=precheck_reason,
                    route=route,
                )
                yield emit(
                    "status",
                    {
                        "step": "precheck_end",
                        "action": precheck_action,
                        "reason": precheck_reason,
                        "message": f"Pre-check complete: {precheck_action}",
                    },
                )
            elif action.name == "gate":
                gate_res = state.get("gate_result")
                self.db_logger.log_gate(run_id=run_id, gate_result=gate_res, attempt=state.get("attempt", 1))
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
                rewrite_res = state.get("rewrite_result")
                if rewrite_res:
                    self.db_logger.log_rewrite(run_id=run_id, attempt=state.get("attempt", 1), rewritten=rewrite_res)
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
                self.db_logger.log_retrieval(
                    run_id=run_id,
                    attempt=state.get("attempt", 1),
                    query=state.get("query"),
                    rewritten_query=state.get("rewritten_query"),
                    sources=sources,
                    retrieval_stats=state.get("retrieval_stats"),
                    source_rank_fields=state.get("source_rank_fields"),
                    candidates=state.get("retrieval_candidates"),
                    candidate_rank_fields=state.get("retrieval_candidate_rank_fields"),
                    prompt_tokens=state.get("retrieval_prompt_tokens"),
                    cost_usd=state.get("retrieval_cost_usd"),
                    model_name=self.settings.embedding_model,
                )
                yield emit(
                    "status",
                    {
                        "step": "retrieval_end",
                        "sources_count": len(sources),
                        "sources": [s.model_dump(mode="json") for s in sources],
                        "message": f"Found {len(sources)} relevant document matches.",
                    },
                )
            elif action.name == "assess_evidence":
                assessment = state.get("evidence_assessment")
                if assessment:
                    self.db_logger.log_evidence_assessment(run_id=run_id, assessment=assessment, attempt=state.get("attempt", 1))
                yield emit(
                    "status",
                    {
                        "step": "assess_evidence_end",
                        "is_sufficient": assessment.is_sufficient if assessment else True,
                        "message": "Evidence sufficiency evaluated successfully.",
                    },
                )
            elif action.name == "verify_and_evaluate":
                citations_res = state.get("citation_map_result")
                ground_res = state.get("groundedness_result")
                if citations_res:
                    self.db_logger.log_citation_verification(run_id=run_id, verification=citations_res, attempt=state.get("attempt", 1))
                if ground_res:
                    self.db_logger.log_groundedness(run_id=run_id, groundedness=ground_res, attempt=state.get("attempt", 1))
                yield emit(
                    "status",
                    {
                        "step": "verify_citations_end",
                        "has_valid_citations": citations_res.has_valid_citations if citations_res else True,
                        "message": f"Citations verified: {'VALID' if (citations_res and citations_res.has_valid_citations) else 'INVALID'}",
                    },
                )
                yield emit(
                    "status",
                    {
                        "step": "evaluate_groundedness_end",
                        "score": ground_res.score if ground_res else 1.0,
                        "message": f"Groundedness score: {ground_res.score if ground_res else 1.0:.2f}",
                    },
                )
            elif action.name == "synthesize":
                self.db_logger.log_synthesis(
                    run_id=run_id,
                    attempt=state.get("attempt", 1),
                    synthesis_result=state.get("synthesis_result"),
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
                decision_res = state.get("decision_result")
                if decision_res:
                    self.db_logger.log_evaluation(
                        run_id=run_id,
                        attempt=state.get("attempt", 1),
                        decision=decision_res,
                    )

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
                    
                    # Update Letta persistent memory (Phase 2)
                    if self.memory_manager and project_id:
                        try:
                            self.memory_manager.update_user_memory(project_id, query=stripped, answer=final_answer)
                        except Exception as e:
                            logger.warning("Failed to update Letta memory: %s", e)

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
                    
                    # Calculate total tokens (input + output)
                    total_tokens = state.get("input_tokens", 0) + count_tokens_fallback(
                        final_answer or "", self.settings.local_llm_rewriter_model
                    )
                    self.db_logger.end_run(
                        run_id=run_id,
                        final_route=response.route,
                        final_answer=response.answer,
                        final_confidence=response.confidence,
                        attempts_count=response.attempts,
                        disclaimer_appended=response.disclaimer_appended,
                        total_cost_usd=state.get("cost_usd", 0.0),
                        total_tokens=total_tokens,
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
                    
                    total_tokens = state.get("input_tokens", 0) + count_tokens_fallback(
                        final_answer or "", self.settings.local_llm_rewriter_model
                    )
                    self.db_logger.end_run(
                        run_id=run_id,
                        final_route=response.route,
                        final_answer=response.answer,
                        final_confidence=response.confidence,
                        attempts_count=response.attempts,
                        disclaimer_appended=response.disclaimer_appended,
                        total_cost_usd=state.get("cost_usd", 0.0),
                        total_tokens=total_tokens,
                    )
                    yield emit("result", response.model_dump(mode="json"))
                    break

            if not app.has_next_action():
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
