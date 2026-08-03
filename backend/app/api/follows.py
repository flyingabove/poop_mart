from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.dependencies import get_current_user
from backend.app.follows.service import (
    FollowError,
    follow_series,
    follow_user,
    list_followed_series,
    list_followed_users,
    unfollow_series,
    unfollow_user,
)

router = APIRouter()


@router.get("/follows/series")
async def get_followed_series(user: dict = Depends(get_current_user)):
    return {"series": list_followed_series(user["id"])}


@router.post("/follows/series/{series_id}", status_code=201)
async def post_follow_series(series_id: str, user: dict = Depends(get_current_user)):
    try:
        return follow_series(user["id"], series_id)
    except FollowError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/follows/series/{series_id}")
async def delete_follow_series(series_id: str, user: dict = Depends(get_current_user)):
    if not unfollow_series(user["id"], series_id):
        raise HTTPException(status_code=404, detail="not following this series")
    return {"series_id": series_id, "following": False}


@router.get("/follows/users")
async def get_followed_users(user: dict = Depends(get_current_user)):
    return {"users": list_followed_users(user["id"])}


@router.post("/follows/users/{followed_id}", status_code=201)
async def post_follow_user(followed_id: str, user: dict = Depends(get_current_user)):
    try:
        return follow_user(user["id"], followed_id)
    except FollowError as e:
        raise HTTPException(status_code=404 if str(e) == "user not found" else 422, detail=str(e))


@router.delete("/follows/users/{followed_id}")
async def delete_follow_user(followed_id: str, user: dict = Depends(get_current_user)):
    if not unfollow_user(user["id"], followed_id):
        raise HTTPException(status_code=404, detail="not following this user")
    return {"followed_id": followed_id, "following": False}
