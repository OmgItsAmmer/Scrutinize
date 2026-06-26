from dataclasses import dataclass
import time
from typing import Any

import httpx

from app.core.config import Settings

NGROK_SKIP_BROWSER_WARNING = "ngrok-skip-browser-warning"


class LocalLlmError(Exception):
    """Raised when the local Ollama-compatible LLM endpoint fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class LlmResponse:
    """Carries full trace details about an LLM generation call."""

    content: str
    model_name: str
    prompt_system: str
    prompt_user: str
    raw_thinking: str | None = None
    latency_ms: int = 0


class LocalLlmClient:
    """HTTP client for OpenAI-compatible POST /v1/chat/completions (local models via ngrok)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.local_llm_configured:
            raise RuntimeError(
                "A local LLM URL is required for the v2 query pipeline."
            )
        self._timeout = settings.local_llm_timeout_s
        self._url_map = {
            settings.local_llm_gate_model: settings.local_llm_gate_url,
            settings.local_llm_rewriter_model: settings.local_llm_rewriter_url,
            settings.local_llm_decision_model: settings.local_llm_decision_url,
        }
        self._base_url = settings.local_llm_base_url

    def _get_url(self, model: str) -> str:
        base = self._url_map.get(model) or self._base_url
        if not base:
            raise LocalLlmError(f"No local LLM URL configured for model {model}")
        trimmed = base.strip().rstrip("/")
        if trimmed.endswith("/v1/chat/completions"):
            return trimmed
        return f"{trimmed}/v1/chat/completions"

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

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            NGROK_SKIP_BROWSER_WARNING: "true",
        }

        url = self._get_url(model)

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LocalLlmError(
                f"Local LLM request timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LocalLlmError(
                f"Local LLM returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise LocalLlmError("Local LLM request failed") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise LocalLlmError("Local LLM returned non-JSON response") from exc

        try:
            message = body["choices"][0]["message"]
            text = str(message["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalLlmError(f"Unexpected response format from local LLM: {body}") from exc

        if not text:
            raise LocalLlmError("Local LLM returned an empty response")

        raw_thinking = message.get("reasoning_content") or message.get("reasoning")
        if raw_thinking:
            raw_thinking = str(raw_thinking).strip()

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return LlmResponse(
            content=text,
            model_name=model,
            prompt_system=system,
            prompt_user=user,
            raw_thinking=raw_thinking,
            latency_ms=latency_ms,
        )
