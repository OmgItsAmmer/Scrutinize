from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class LlmResponse:
    """Carries full trace details about an LLM generation call."""
    content: str
    model_name: str
    prompt_system: str
    prompt_user: str
    raw_thinking: str | None = None
    latency_ms: int = 0

class BaseLlmClient(ABC):
    """Abstract base interface for V2 LLM clients (Local or Cloud)."""

    @abstractmethod
    def generate(
        self,
        model: str,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
    ) -> LlmResponse:
        """Generate a response given a system and user prompt."""
        pass
