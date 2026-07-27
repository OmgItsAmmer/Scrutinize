import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _env_files() -> tuple[str, ...]:
    """Load repo-root .env when scripts run from backend/ (see Makefile)."""
    candidates = (
        _REPO_ROOT / ".env",
        _BACKEND_ROOT / ".env",
        Path(".env"),
    )
    return tuple(str(path) for path in candidates if path.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files() or (".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Scrutinize"
    environment: str = "development"
    debug: bool = False

    # Neon Postgres — set via .env (pooled connection string recommended).
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    openai_api_key: str = ""

    # Per-person authentication and OTP email verification.
    jwt_secret_key: str = "change-me-in-production"
    jwt_expiry_minutes: int = 60 * 24
    otp_expiry_minutes: int = 15
    resend_api_key: str = ""
    email_from: str = "Scrutinize <onboarding@resend.dev>"
    google_client_id: str = ""

    # Embeddings & Qdrant (M5)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100
    qdrant_collection: str = "segments"

    # Text ingestion (M2)
    text_chunk_size: int = 400
    text_chunk_overlap: int = 50
    max_upload_bytes: int = 10 * 1024 * 1024

    # Audio ingestion (M3)
    whisper_model: str = "whisper-1"
    audio_segment_min_seconds: float = 15.0
    audio_segment_max_seconds: float = 30.0

    # Video ingestion (M4)
    vision_model: str = "gpt-4o-mini"
    video_keyframe_interval_seconds: float = 5.0
    video_max_keyframes: int = 8
    video_keyframe_max_width: int = 512
    vision_call_delay_seconds: float = 2.0
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    # OpenAI retry — workers retry 429 TPM/RPM instead of failing the job.
    openai_max_retries: int = 8
    openai_retry_min_delay_seconds: float = 2.0


    # Local LLM pipeline (v2 — M6)
    local_llm_base_url: str = ""
    local_llm_gate_url: str = ""
    local_llm_rewriter_url: str = ""
    local_llm_decision_url: str = ""
    local_llm_rewriter_model: str = "Qwen/Qwen3.5-2B"
    local_llm_gate_model: str = "Qwen/Qwen3.5-2B"
    local_llm_decision_model: str = "qwen3.5:4b"
    local_llm_timeout_s: float = 120.0

    # PDF rename agent (separate from the main pipeline LLMs)
    pdf_renamer_base_url: str = ""
    pdf_renamer_model: str = ""
    pdf_renamer_timeout_s: float = 60.0

    # v2 pipeline tuning
    use_cloud_llm: bool = False
    v2_max_pipeline_attempts: int = 2
    v2_confidence_threshold: float = 0.7
    v2_rrf_top_k: int = 5
    v2_rrf_k: int = 60
    v2_conversation_window_size: int = 10  # max chat exchanges kept (2 messages each)
    v2_retrieval_precheck_high_score: float = 0.025
    v2_retrieval_precheck_low_score: float = 0.012

    # MCP Configurations
    mcp_pdf_server_enabled: bool = True

    # Web Search Configurations
    brave_search_api_key: str = ""
    tavily_api_key: str = ""
    enable_web_search: bool = True
    web_search_engine: str = "brave"  # "brave" or "tavily"
    jina_reader_token: str = ""

    # Letta & Graphiti Memory Configurations
    letta_api_url: str = "http://localhost:8283"
    letta_api_key: str = ""
    graphiti_neo4j_uri: str = "bolt://localhost:7687"
    graphiti_neo4j_user: str = "neo4j"
    graphiti_neo4j_password: str = ""

    # LangSmith tracing config
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "scrutinize"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Cloudinary — raw file uploads (text, audio, video); relational data lives in Neon.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "scrutinize"

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Accept JSON arrays or comma-separated origins (Fly/PowerShell-safe)."""
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return []

        # PowerShell / shell quoting sometimes wraps JSON in extra single quotes.
        if (
            (stripped.startswith("'") and stripped.endswith("'"))
            or (stripped.startswith('"') and stripped.endswith('"'))
        ) and len(stripped) >= 2:
            stripped = stripped[1:-1].strip()

        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                msg = "CORS_ORIGINS JSON must be an array of origin strings"
                raise ValueError(msg)
            return [str(origin).strip() for origin in parsed if str(origin).strip()]

        return [origin.strip() for origin in stripped.split(",") if origin.strip()]

    # Rate limiting — protects OpenAI/Whisper quotas from request floods.
    rate_limit_enabled: bool = True
    rate_limit_expensive_requests: int = 10
    rate_limit_expensive_window_seconds: int = 60
    rate_limit_general_requests: int = 120
    rate_limit_general_window_seconds: int = 60
    rate_limit_global_requests: int = 300
    rate_limit_global_window_seconds: int = 60

    # Fly.io Scaling settings
    fly_worker_app_name: str = ""
    fly_api_token: str = ""
    worker_idle_timeout_seconds: int | None = None

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    # Run tasks inline (no Redis broker/worker). Default on in development.
    celery_task_always_eager: bool | None = None

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def task_always_eager(self) -> bool:
        if self.celery_task_always_eager is not None:
            return self.celery_task_always_eager
        return self.environment == "development"

    @property
    def resolved_worker_idle_timeout_seconds(self) -> int:
        """Auto-shutdown idle workers (Fly cost saving). Disabled by default in development."""
        if self.worker_idle_timeout_seconds is not None:
            return self.worker_idle_timeout_seconds
        return 0 if self.environment == "development" else 120

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    @property
    def local_llm_configured(self) -> bool:
        return bool(
            self.local_llm_base_url.strip() or 
            self.local_llm_gate_url.strip() or 
            self.local_llm_rewriter_url.strip() or 
            self.local_llm_decision_url.strip()
        )

    @property
    def pdf_renamer_configured(self) -> bool:
        return bool(self.pdf_renamer_base_url.strip() and self.pdf_renamer_model.strip())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.langsmith_tracing:
        import os
        os.environ["LANGSMITH_TRACING"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        if settings.langsmith_project:
            os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    return settings


def reload_settings() -> Settings:
    """Clear cached settings — call after .env changes (especially Celery workers)."""
    get_settings.cache_clear()
    return get_settings()
