from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.dependencies import get_optional_user
from backend.app.profiles.service import get_profile

router = APIRouter()


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str, viewer: Optional[dict] = Depends(get_optional_user)):
    profile = get_profile(user_id, viewer_id=viewer["id"] if viewer else None)
    if not profile:
        raise HTTPException(status_code=404, detail="user not found")
    return profile
