from fastapi import APIRouter

from app.api.library import router as library_router
from app.api.routes import router as core_router
from app.api.search import router as search_router
from app.api.upload import router as upload_router
from app.api.v2.router import v2_router

api_router = APIRouter()
api_router.include_router(core_router)
api_router.include_router(upload_router)
api_router.include_router(search_router)
api_router.include_router(library_router)
api_router.include_router(v2_router)
