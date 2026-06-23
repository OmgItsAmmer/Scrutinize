from typing import Any

import httpx

from app.core.config import Settings

NGROK_SKIP_BROWSER_WARNING = "ngrok-skip-browser-warning"


class LocalLlmError(Exception):
    """Raised when the local Ollama-compatible LLM endpoint fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LocalLlmClient:
    """HTTP client for Ollama-style POST /api/generate (local models via ngrok)."""

    GENERATE_PATH = "/api/generate"

    def __init__(self, settings: Settings) -> None:
        if not settings.local_llm_configured:
            raise RuntimeError(
                "LOCAL_LLM_BASE_URL is required for the v2 query pipeline."
            )
        self._generate_url = self._normalize_generate_url(settings.local_llm_base_url)
        self._timeout = settings.local_llm_timeout_s

    @staticmethod
    def _normalize_generate_url(base_url: str) -> str:
        """Accept host-only or full /api/generate URL (common ngrok setups)."""
        trimmed = base_url.strip().rstrip("/")
        if trimmed.endswith("/api/generate"):
            return trimmed
        return f"{trimmed}{LocalLlmClient.GENERATE_PATH}"

    @property
    def generate_url(self) -> str:
        return self._generate_url

    def generate(
        self,
        model: str,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": user,
            "stream": False,
        }
        if system.strip():
            payload["system"] = system.strip()
        if json_mode:
            payload["format"] = "json"

        headers = {
            "Content-Type": "application/json",
            NGROK_SKIP_BROWSER_WARNING: "true",
        }

        try:
            response = httpx.post(
                self.generate_url,
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

        text = str(body.get("response", "")).strip()
        if not text:
            # Some thinking models (e.g. qwen3.5 via Ollama) leave response empty.
            text = str(body.get("thinking", "")).strip()
        if not text:
            raise LocalLlmError("Local LLM returned an empty response")
        return text
