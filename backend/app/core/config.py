from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    openai_api_key: str = ""

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
    video_max_keyframes: int = 15
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    # Search & agents (M6)
    router_model: str = "gpt-4o-mini"
    synthesis_model: str = "gpt-4o-mini"
    search_top_k: int = 5

    # Cloudinary — raw file uploads (text, audio, video); relational data lives in Neon.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "scrutinize"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Rate limiting — protects OpenAI/Whisper quotas from request floods.
    rate_limit_enabled: bool = True
    rate_limit_expensive_requests: int = 10
    rate_limit_expensive_window_seconds: int = 60
    rate_limit_general_requests: int = 120
    rate_limit_general_window_seconds: int = 60
    rate_limit_global_requests: int = 300
    rate_limit_global_window_seconds: int = 60

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
