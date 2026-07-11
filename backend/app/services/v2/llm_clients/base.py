from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, List, Optional

@dataclass(frozen=True)
class ToolCall:
    """Carries details about a tool execution request from the LLM."""
    id: str
    name: str
    arguments: dict

@dataclass(frozen=True)
class LlmResponse:
    """Carries full trace details about an LLM generation call."""
    content: str
    model_name: str
    prompt_system: str
    prompt_user: str
    raw_thinking: str | None = None
    latency_ms: int = 0
    tool_calls: Optional[List[ToolCall]] = None

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
        tools: Optional[List[dict]] = None,
    ) -> LlmResponse:
        """Generate a response given a system and user prompt."""
        pass

    @abstractmethod
    def generate_stream(
        self,
        model: str,
        system: str,
        user: str,
    ) -> Iterator[str]:
        """Generate a streamed response token by token."""
        pass

