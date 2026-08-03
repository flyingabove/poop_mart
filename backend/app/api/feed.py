from fastapi import APIRouter, Query
from typing import Optional
from backend.app.feed import service as feed_service

router = APIRouter()


@router.get("/feed")
async def get_feed(
    tab: str = Query("for_you"),
    card_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    cards = feed_service.list_feed(tab=tab, card_type=card_type, limit=limit)
    return {"tab": tab, "count": len(cards), "cards": cards}
