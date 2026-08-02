from fastapi import APIRouter

from app.api.v3.conversations import router as conversations_router
from app.api.v3.approvals import router as approvals_router
from app.api.v3.projects import router as projects_router
from app.api.v3.debug import router as debug_router

v3_router = APIRouter(prefix="/v3")
v3_router.include_router(conversations_router)
v3_router.include_router(approvals_router)
v3_router.include_router(projects_router, prefix="/projects")
v3_router.include_router(debug_router)
