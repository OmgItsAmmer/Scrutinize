import os
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.core.database import (  # noqa: E402
    get_session,
    init_db,
    normalize_database_url,
    reset_engine,
    set_engine,
)
from app.main import create_app  # noqa: E402
from app.models.file import File  # noqa: E402
from app.models.processing_job import ProcessingJob  # noqa: E402
from app.models.segment import Segment  # noqa: E402
from app.schemas.health import DependencyCheck  # noqa: E402


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # Satisfy Settings validation without opening a real Postgres connection in unit tests.
    if not os.getenv("DATABASE_URL"):
        monkeypatch.setenv("DATABASE_URL", "sqlite://")
    yield


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    reset_engine()
    yield
    get_settings.cache_clear()
    reset_engine()


@pytest.fixture(autouse=True)
def mock_external_dependencies(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    if request.node.get_closest_marker("integration"):
        yield
        return

    with (
        patch("app.services.health.check_redis", return_value=DependencyCheck(status="ok")),
        patch("app.services.health.check_qdrant", return_value=DependencyCheck(status="ok")),
    ):
        yield


def _sqlite_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(name="engine")
def engine_fixture(request: pytest.FixtureRequest):
    is_integration = request.node.get_closest_marker("integration") is not None
    database_url = os.getenv("DATABASE_URL", "")

    if is_integration and database_url.startswith("postgresql"):
        engine = create_engine(
            normalize_database_url(database_url),
            pool_pre_ping=True,
        )
    else:
        engine = _sqlite_engine()

    set_engine(engine)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    reset_engine()


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    init_db()
    app = create_app()

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="api_base_url")
def api_base_url_fixture() -> str:
    return os.getenv("VITE_API_URL", "http://localhost:8000")
