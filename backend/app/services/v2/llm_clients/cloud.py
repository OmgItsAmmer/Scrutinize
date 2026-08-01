import time
import logging
from typing import Any, Iterator
from langsmith import traceable

from openai import OpenAI
from app.core.config import Settings
from app.services.openai_retry import call_with_retry
from app.services.v2.llm_clients.base import BaseLlmClient, LlmResponse

logger = logging.getLogger(__name__)

_JSON_MODE_HINT = "Respond with a valid JSON object only."


def _ensure_json_mode_hint(messages: list[dict[str, str]]) -> None:
    """OpenAI requires the word 'json' in messages when using json_object format."""
    if any("json" in msg["content"].lower() for msg in messages):
        return
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = f"{messages[0]['content'].rstrip()}\n\n{_JSON_MODE_HINT}"
    else:
        messages.insert(0, {"role": "system", "content": _JSON_MODE_HINT})


class CloudLlmError(Exception):
    """Raised when the cloud LLM endpoint fails."""
    pass


class CloudLlmClient(BaseLlmClient):
    """Client for Cloud LLMs (OpenAI) that matches the V2 pipeline interface."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for the v2 query pipeline when using CloudLlmClient.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._max_retries = settings.openai_max_retries
        self._min_delay_seconds = settings.openai_retry_min_delay_seconds

    @traceable(name="CloudLlmClient.generate", run_type="llm")
    def generate(
        self,
        model: str,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        tools: list[dict] | None = None,
    ) -> LlmResponse:
        start_time = time.perf_counter()

        messages = []
        if system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": user.strip()})
        
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            _ensure_json_mode_hint(messages)
            kwargs["response_format"] = {"type": "json_object"}
            kwargs["messages"] = messages
        if tools:
            kwargs["tools"] = tools
            
        def _call_openai() -> Any:
            return self._client.chat.completions.create(**kwargs)

        try:
            response = call_with_retry(
                _call_openai,
                max_retries=self._max_retries,
                min_delay_seconds=self._min_delay_seconds,
                label=f"openai-v2-{model}"
            )
        except Exception as exc:
            raise CloudLlmError(f"Cloud LLM request failed: {exc}") from exc

        try:
            message = response.choices[0].message
            text = str(message.content or "").strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise CloudLlmError(f"Unexpected response format from Cloud LLM") from exc

        # Parse tool calls
        tool_calls = None
        if hasattr(message, "tool_calls") and message.tool_calls:
            import json
            from app.services.v2.llm_clients.base import ToolCall
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args
                ))

        if not text and not tool_calls:
            raise CloudLlmError("Cloud LLM returned an empty response with no tool calls")

        # OpenAI o1/o3 models may include reasoning_content or similar in the future,
        # but for now, standard models don't return raw thinking in the same way DeepSeek does.
        raw_thinking = None

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
            details = getattr(response.usage, "prompt_tokens_details", None)
            if details:
                cached_tokens = getattr(details, "cached_tokens", 0) or 0

        return LlmResponse(
            content=text,
            model_name=model,
            prompt_system=system,
            prompt_user=user,
            raw_thinking=raw_thinking,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
        )

    @traceable(name="CloudLlmClient.generate_stream", run_type="llm")
    def generate_stream(
        self,
        model: str,
        system: str,
        user: str,
    ) -> Iterator[str]:
        messages = []
        if system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": user.strip()})
        
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            raise CloudLlmError(f"Cloud LLM streaming failed: {exc}") from exc

