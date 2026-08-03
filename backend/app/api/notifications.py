from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.auth.dependencies import get_current_user
from backend.app.notifications.service import list_notifications, mark_read, unread_count

router = APIRouter()


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
