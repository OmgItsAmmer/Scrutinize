from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.access_log import quiet_poll_access_logs
from app.core.config import get_settings
from app.core.database import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.file import File  # noqa: F401
from app.models.pipeline_log import (  # noqa: F401
    PipelineRun,
    PipelineStep,
)
from app.models.processing_job import ProcessingJob  # noqa: F401
from app.models.segment import Segment  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.environment == "development":
        quiet_poll_access_logs()
    if not settings.database_url.strip():
        msg = (
            "DATABASE_URL is required. Set it via fly secrets set -a scrutinize-api "
            "DATABASE_URL=..."
        )
        logger.error(msg)
        raise RuntimeError(msg)
    try:
        init_db()
    except Exception:
        logger.exception("Database init failed — check DATABASE_URL and Neon connectivity")
        raise
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
    app.add_middleware(RateLimitMiddleware)

    app.include_router(api_router)
    return app


app = create_app()
