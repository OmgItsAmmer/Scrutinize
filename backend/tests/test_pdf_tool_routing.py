from app.services.v2.pipeline_orchestrator import PipelineOrchestrator
from app.services.v2.rag_gate import RagGate, GateResult


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


def test_gate_tool_request_forces_rag_route():
    client = FakeGateClient(
        """
        {
          "route": "generic",
          "reason": "PDF generation requested for tech news.",
          "requested_tool": "generate_pdf",
          "reply": "I cannot create PDFs."
        }
        """
    )
    gate = RagGate(client, FakeSettings())

    result = gate.classify(
        "prepare a downloadable brief on AI chip news",
        tool_context="- generate_pdf: Create a downloadable PDF document.",
    )

    assert result.route == "rag"
    assert result.reply is None
    assert result.requested_tool == "generate_pdf"
    assert "generate_pdf" in client.system


def test_orchestrator_pdf_request_comes_from_gate_tool_field():
    assert PipelineOrchestrator._requested_pdf(
        GateResult(
            route="rag",
            reason="Tool request.",
            requested_tool="generate_pdf",
        )
    )
    assert not PipelineOrchestrator._requested_pdf(
        GateResult(route="generic", reason="No tool requested.")
    )
