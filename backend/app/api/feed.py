from fastapi import APIRouter, Depends, Query
from typing import Optional
from backend.app.auth.dependencies import get_optional_user
from backend.app.feed import service as feed_service
from backend.app.follows.service import followed_series_ids

router = APIRouter()


@router.get("/feed")
async def get_feed(
    tab: str = Query("for_you"),
    card_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[dict] = Depends(get_optional_user),
):
    followed = followed_series_ids(user["id"]) if user else None
    cards = feed_service.list_feed(tab=tab, card_type=card_type, limit=limit, followed_series=followed)
    return {
        "tab": tab,
        "count": len(cards),
        "personalized": bool(followed),
        "cards": cards,
    }
