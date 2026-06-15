from fastapi import APIRouter, Depends

from app.core.deps import get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.post("/search", response_model=SearchResponse, tags=["search"])
def search(
    body: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return search_service.search(
        body.query,
        modality_filter=body.modality_filter,
        top_k=body.top_k,
    )
