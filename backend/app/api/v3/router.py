from fastapi import APIRouter

from app.api.v3.conversations import router as conversations_router
from app.api.v3.approvals import router as approvals_router

v3_router = APIRouter(prefix="/v3")
v3_router.include_router(conversations_router)
v3_router.include_router(approvals_router)
