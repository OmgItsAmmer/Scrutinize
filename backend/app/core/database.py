from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_engine = None


def normalize_database_url(url: str) -> str:
    """Normalize SQLAlchemy URL for Neon Postgres (psycopg driver + SSL)."""
    normalized = url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql+psycopg://" + normalized.removeprefix("postgres://")
    elif normalized.startswith("postgresql://"):
        normalized = "postgresql+psycopg://" + normalized.removeprefix("postgresql://")

    if "neon.tech" in normalized and "sslmode=" not in normalized:
        separator = "&" if "?" in normalized else "?"
        normalized = f"{normalized}{separator}sslmode=require"

    return normalized


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            normalize_database_url(settings.database_url),
            echo=settings.debug,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 15},
        )
    return _engine


def set_engine(engine) -> None:
    global _engine
    _engine = engine


def reset_engine() -> None:
    global _engine
    _engine = None


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
