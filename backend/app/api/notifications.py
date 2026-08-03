from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.notifications.service import (
    get_preferences,
    list_notifications,
    mark_read,
    set_preference,
    unread_count,
)

router = APIRouter()


class PreferenceIn(BaseModel):
    enabled: bool


@router.get("/notifications")
async def get_notifications(unread_only: bool = Query(False), user: dict = Depends(get_current_user)):
    return {
        "unread_count": unread_count(user["id"]),
        "notifications": list_notifications(user["id"], unread_only=unread_only),
    }


@router.post("/notifications/{notification_id}/read")
async def post_mark_read(notification_id: int, user: dict = Depends(get_current_user)):
    if not mark_read(user["id"], notification_id):
        raise HTTPException(status_code=404, detail="notification not found or already read")
    return {"id": notification_id, "read": True}


@router.get("/notifications/preferences")
async def get_notification_preferences(user: dict = Depends(get_current_user)):
    return {"preferences": get_preferences(user["id"])}


@router.put("/notifications/preferences/{category}")
async def put_notification_preference(category: str, body: PreferenceIn, user: dict = Depends(get_current_user)):
    try:
        return set_preference(user["id"], category, body.enabled)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
