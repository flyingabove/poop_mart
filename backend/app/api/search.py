from fastapi import APIRouter, Query
from backend.app.search import service as search_service

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=1)):
    return search_service.search(q)
