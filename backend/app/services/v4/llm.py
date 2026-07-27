from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from app.core.config import Settings


def get_pydantic_ai_model(model_name: str, settings: Settings, use_cloud_llm: bool = False) -> OpenAIChatModel:
    """Constructs a PydanticAI OpenAIChatModel based on configuration and the use_cloud_llm selection.

    If use_cloud_llm is True, routes requests to OpenAI.
    Otherwise, routes requests to the configured local Ollama/OpenAI-compatible server.
    """
    if use_cloud_llm:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is not configured for cloud LLM services.")
        # Ensure we have a valid cloud model name
        cloud_model = model_name if model_name and not model_name.startswith("Qwen") else "gpt-4o-mini"
        provider = OpenAIProvider(api_key=settings.openai_api_key)
        return OpenAIChatModel(
            model_name=cloud_model,
            provider=provider,
        )
    else:
        # Determine local URL corresponding to model
        url = ""
        if model_name == settings.local_llm_gate_model:
            url = settings.local_llm_gate_url
        elif model_name == settings.local_llm_rewriter_model:
            url = settings.local_llm_rewriter_url
        elif model_name == settings.local_llm_decision_model:
            url = settings.local_llm_decision_url

        if not url.strip():
            url = settings.local_llm_base_url or "http://localhost:11434/v1"

        trimmed = url.strip().rstrip("/")
        # PydanticAI / OpenAI client expects a base URL pointing to /v1 or Ollama base.
        # If it has /chat/completions, strip it.
        if trimmed.endswith("/chat/completions"):
            trimmed = trimmed[:-17]  # strip "/chat/completions"
        elif trimmed.endswith("/v1/chat/completions"):
            trimmed = trimmed[:-20]  # strip "/v1/chat/completions"

        local_model = model_name or settings.local_llm_gate_model or "qwen3.5:4b"
        provider = OpenAIProvider(
            base_url=trimmed,
            api_key=settings.openai_api_key or "mock-key",
        )
        return OpenAIChatModel(
            model_name=local_model,
            provider=provider,
        )
