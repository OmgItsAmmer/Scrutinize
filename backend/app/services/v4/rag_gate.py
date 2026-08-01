import logging
from langsmith import traceable
from pydantic_ai import Agent

from app.core.config import Settings
from app.schemas.v4.rag import GateResult
from app.services.v2.prompts import load_prompt
from app.services.v2.conversation_format import append_conversation_context
from app.services.v4.llm import get_pydantic_ai_model

logger = logging.getLogger(__name__)


class RagGate:
    """Route generic vs RAG/web using the current query and full conversation snapshot."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("rag_gate_system.txt")

    @traceable(name="RagGate.classify", run_type="chain")
    def classify(
        self,
        original: str,
        *,
        use_cloud_llm: bool = False,
        model: str | None = None,
        system_override: str | None = None,
        conversation_context: str = "",
        tool_context: str = "",
        client_requested_tool: str | None = None,
    ) -> GateResult:
        effective_model = model or self._model
        effective_system = system_override or self._system
        if tool_context.strip():
            effective_system = f"{effective_system}\n\nAvailable application tools:\n{tool_context.strip()}"

        user_lines = [f"Current user query: {original.strip()}"]
        if client_requested_tool:
            user_lines.append(
                f"User selected tool in UI: {client_requested_tool.strip()} "
                "(consider this when choosing route and requested_tool)."
            )
        append_conversation_context(user_lines, conversation_context)
        user_prompt = "\n".join(user_lines)

        try:
            # Dynamically resolve PydanticAI model
            pydantic_model = get_pydantic_ai_model(
                model_name=effective_model,
                settings=self._settings,
                use_cloud_llm=use_cloud_llm,
            )

            # Create PydanticAI Agent
            agent = Agent(
                model=pydantic_model,
                output_type=GateResult,
                system_prompt=effective_system,
            )

            logger.info(
                "Running RAG Gate classification with model=%s, use_cloud_llm=%s",
                effective_model,
                use_cloud_llm,
            )
            result = agent.run_sync(user_prompt)
            gate_res = result.output

            # Enforce gate prompt rules: reply is only for generic route
            if gate_res.route != "generic":
                gate_res = GateResult(
                    route=gate_res.route,
                    reason=gate_res.reason,
                    requested_tool=gate_res.requested_tool,
                    reply=None,
                )

            # Construct LlmResponse and attach it
            from app.services.v2.llm_clients.base import LlmResponse
            usage = result.usage
            prompt_tokens = (usage.input_tokens or 0) if usage else 0
            completion_tokens = (usage.output_tokens or 0) if usage else 0
            cached_tokens = 0
            if usage and usage.details and isinstance(usage.details, dict):
                cached_tokens = usage.details.get("cached_tokens", 0) or 0

            gate_res.llm_call = LlmResponse(
                content=gate_res.model_dump_json() if hasattr(gate_res, "model_dump_json") else str(gate_res),
                model_name=effective_model,
                prompt_system=effective_system,
                prompt_user=user_prompt,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
            )
            return gate_res

        except Exception as exc:
            logger.warning(
                "PydanticAI RAG gate generation/parse failed; defaulting to generic: %s", exc
            )
            return GateResult(
                route="generic",
                reason=f"Gate failed; defaulting to generic: {exc}",
                reply=None,
            )
