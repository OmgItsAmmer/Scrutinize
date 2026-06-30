from fastapi import APIRouter

from app.api.v2.llm_health import router as llm_health_router
from app.api.v2.projects import router as projects_router
from app.api.v2.search import router as search_router
from app.api.v2.upload import router as upload_router

v2_router = APIRouter(prefix="/v2")
v2_router.include_router(llm_health_router)
v2_router.include_router(search_router)
v2_router.include_router(projects_router)
v2_router.include_router(upload_router)
