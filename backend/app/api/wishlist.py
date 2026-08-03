from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.wishlist.service import WishlistError, add_item, list_wishlist, remove_item

router = APIRouter()


class WishlistItemIn(BaseModel):
    figure_id: str
    alert_threshold: Optional[float] = None


@router.get("/wishlist")
async def get_wishlist(user: dict = Depends(get_current_user)):
    return {"items": list_wishlist(user["id"])}


@router.post("/wishlist", status_code=201)
async def post_wishlist(body: WishlistItemIn, user: dict = Depends(get_current_user)):
    try:
        return add_item(user["id"], body.figure_id, body.alert_threshold)
    except WishlistError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/wishlist/{figure_id}")
async def delete_wishlist_item(figure_id: str, user: dict = Depends(get_current_user)):
    if not remove_item(user["id"], figure_id):
        raise HTTPException(status_code=404, detail="item not in wishlist")
    return {"removed": figure_id}
