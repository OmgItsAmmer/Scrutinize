import time
import logging
from typing import Any

from openai import OpenAI
from app.core.config import Settings
from app.services.openai_retry import call_with_retry
from app.services.v2.llm_clients.base import BaseLlmClient, LlmResponse

logger = logging.getLogger(__name__)

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

    def generate(
        self,
        model: str,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
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
            kwargs["response_format"] = {"type": "json_object"}
            
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
            text = str(message.content).strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise CloudLlmError(f"Unexpected response format from Cloud LLM") from exc

        if not text:
            raise CloudLlmError("Cloud LLM returned an empty response")

        # OpenAI o1/o3 models may include reasoning_content or similar in the future,
        # but for now, standard models don't return raw thinking in the same way DeepSeek does.
        raw_thinking = None

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return LlmResponse(
            content=text,
            model_name=model,
            prompt_system=system,
            prompt_user=user,
            raw_thinking=raw_thinking,
            latency_ms=latency_ms,
        )
