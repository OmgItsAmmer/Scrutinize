import time
from typing import Any, Iterator
import httpx
from langsmith import traceable

from app.core.config import Settings
from app.services.v2.llm_clients.base import BaseLlmClient, LlmResponse

NGROK_SKIP_BROWSER_WARNING = "ngrok-skip-browser-warning"


class LocalLlmError(Exception):
    """Raised when the local Ollama-compatible LLM endpoint fails."""
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LocalLlmClient(BaseLlmClient):
    """HTTP client for OpenAI-compatible POST /v1/chat/completions (local models via ngrok)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.local_llm_configured:
            raise RuntimeError(
                "A local LLM URL is required for the v2 query pipeline when using LocalLlmClient."
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

    @traceable(name="LocalLlmClient.generate", run_type="llm")
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

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools

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
            text = str(message.get("content") or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalLlmError(f"Unexpected response format from local LLM: {body}") from exc

        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            import json
            from app.services.v2.llm_clients.base import ToolCall
            tool_calls = []
            for tc in message["tool_calls"]:
                try:
                    args_raw = tc["function"]["arguments"]
                    if isinstance(args_raw, str):
                        args = json.loads(args_raw)
                    else:
                        args = args_raw
                except Exception:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=args
                ))

        if not text and not tool_calls:
            raise LocalLlmError("Local LLM returned an empty response with no tool calls")

        raw_thinking = message.get("reasoning_content") or message.get("reasoning")
        if raw_thinking:
            raw_thinking = str(raw_thinking).strip()

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0
        usage_dict = body.get("usage") or {}
        if usage_dict:
            prompt_tokens = usage_dict.get("prompt_tokens", 0) or 0
            completion_tokens = usage_dict.get("completion_tokens", 0) or 0
            details = usage_dict.get("prompt_tokens_details", {})
            if isinstance(details, dict):
                cached_tokens = details.get("cached_tokens", 0) or 0

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

    @traceable(name="LocalLlmClient.generate_stream", run_type="llm")
    def generate_stream(
        self,
        model: str,
        system: str,
        user: str,
    ) -> Iterator[str]:
        import json
        messages = []
        if system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": user.strip()})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
            NGROK_SKIP_BROWSER_WARNING: "true",
        }

        url = self._get_url(model)

        try:
            with httpx.stream(
                "POST",
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data["choices"][0]["delta"].get("content")
                            if content:
                                yield content
                        except Exception:
                            pass
        except httpx.TimeoutException as exc:
            raise LocalLlmError(f"Local LLM request timed out after {self._timeout}s") from exc
        except httpx.HTTPStatusError as exc:
            raise LocalLlmError(
                f"Local LLM returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise LocalLlmError("Local LLM request failed") from exc

