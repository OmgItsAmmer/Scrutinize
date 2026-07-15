from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.v2.rag_gate import RagGate, GateResult
from app.services.v2.retrieval_precheck import RetrievalPrecheck
from app.services.v2.mcp_manager import McpClientManager


class FakeGateClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.system = ""

    def generate(self, model, system, user, *, json_mode=False, tools=None):
        from app.services.v2.llm_clients.base import LlmResponse

        self.system = system
        return LlmResponse(
            content=self.content,
            model_name=model,
            prompt_system=system,
            prompt_user=user,
        )


class FakeSettings:
    local_llm_gate_model = "fake-gate"
    v2_retrieval_precheck_high_score = 0.025
    v2_retrieval_precheck_low_score = 0.012


def test_gate_flowchart_tool_request_preserves_gate_route():
    client = FakeGateClient(
        """
        {
          "route": "generic",
          "reason": "Flowchart generation requested for tech process.",
          "requested_tool": "generate_flowchart",
          "reply": "I cannot create flowcharts."
        }
        """
    )
    gate = RagGate(client, FakeSettings())

    result = gate.classify(
        "draw a sequence diagram for the search pipeline",
        tool_context="- generate_flowchart: Create a flowchart diagram.",
    )

    assert result.route == "generic"
    assert result.reply == "I cannot create flowcharts."
    assert result.requested_tool == "generate_flowchart"
    assert "generate_flowchart" in client.system


def test_orchestrator_flowchart_request_comes_from_gate_tool_field():
    assert PipelineOrchestrator._requested_flowchart(
        GateResult(
            route="rag",
            reason="Tool request.",
            requested_tool="generate_flowchart",
        )
    )
    assert not PipelineOrchestrator._requested_flowchart(
        GateResult(route="generic", reason="No tool requested.")
    )


def test_orchestrator_forces_rag_when_gate_misroutes_flowchart_tool():
    gate_result = GateResult(
        route="generic",
        reason="Flowchart generation requested.",
        requested_tool="generate_flowchart",
        reply="Use the tool.",
    )
    forced = PipelineOrchestrator._maybe_force_rag_for_tool(
        gate_result,
        client_requested_tool="generate_flowchart",
    )
    assert forced.route == "rag"
    assert forced.requested_tool == "generate_flowchart"
    assert forced.reply is None


def test_orchestrator_forces_rag_from_client_flowchart_tool_even_without_gate_tool_field():
    gate_result = GateResult(
        route="generic",
        reason="Generic reply.",
        reply="Hello.",
    )
    forced = PipelineOrchestrator._maybe_force_rag_for_tool(
        gate_result,
        client_requested_tool="generate_flowchart",
    )
    assert forced.route == "rag"
    assert forced.requested_tool == "generate_flowchart"
    assert forced.reply is None
