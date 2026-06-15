from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # Cloudinary — raw file uploads (text, audio, video); relational data lives in Neon.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "scrutinize"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

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
