from app.core.config import Settings
from app.services.v2.conversation_format import append_conversation_context
from app.services.v2.local_llm_client import LocalLlmClient
from app.services.v2.prompts import load_prompt


class GenericAgent:
    """qwen3.5:0.8b — natural reply when the gate omits a generic reply."""

    def __init__(self, client: LocalLlmClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.local_llm_gate_model
        self._system = load_prompt("generic_agent_system.txt")

    def reply(self, query: str, *, conversation_context: str = "") -> str:
        user_lines = [query.strip()]
        append_conversation_context(user_lines, conversation_context)
        return self._client.generate(
            self._model,
            self._system,
            "\n".join(user_lines),
        )
