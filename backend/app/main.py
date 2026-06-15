from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.models.file import File  # noqa: F401
from app.models.processing_job import ProcessingJob  # noqa: F401
from app.models.segment import Segment  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if not settings.database_url.strip():
        raise RuntimeError(
            "DATABASE_URL is required. Add your Neon Postgres connection string to .env "
            "(see .env.example)."
        )
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
