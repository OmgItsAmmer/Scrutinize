from fastapi import APIRouter

from app.api.routes import router as core_router
from app.api.upload import router as upload_router

api_router = APIRouter()
api_router.include_router(core_router)
api_router.include_router(upload_router)
