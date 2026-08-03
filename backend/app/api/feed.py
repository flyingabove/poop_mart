from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from backend.app.auth.dependencies import get_current_user, get_optional_user
from backend.app.feed import service as feed_service
from backend.app.follows.service import followed_series_ids, followed_user_ids
from backend.app.notifications.service import notify_followers_of_user_post

router = APIRouter()


class CommunityPostIn(BaseModel):
    figure_id: str
    title: str
    body: str


@router.get("/feed")
async def get_feed(
    tab: str = Query("for_you"),
    card_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[dict] = Depends(get_optional_user),
):
    followed_series = followed_series_ids(user["id"]) if user else None
    followed_creators = followed_user_ids(user["id"]) if user else None
    cards = feed_service.list_feed(
        tab=tab,
        card_type=card_type,
        limit=limit,
        followed_series=followed_series,
        followed_users=followed_creators,
    )
    return {
        "tab": tab,
        "count": len(cards),
        "personalized": bool(followed_series or followed_creators),
        "cards": cards,
    }


@router.post("/feed/posts", status_code=201)
async def post_community_post(body: CommunityPostIn, user: dict = Depends(get_current_user)):
    try:
        post = feed_service.create_community_post(user["id"], body.figure_id, body.title, body.body)
    except feed_service.FeedError as e:
        raise HTTPException(status_code=422, detail=str(e))
    notify_followers_of_user_post(user["id"], post["id"], body.figure_id, post["series_id"], body.title)
    return post


@router.delete("/feed/posts/{post_id}")
async def delete_community_post(post_id: str, user: dict = Depends(get_current_user)):
    if not feed_service.remove_post(user["id"], post_id):
        raise HTTPException(status_code=404, detail="post not found")
    return {"id": post_id, "removed": True}
