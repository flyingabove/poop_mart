from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.collections.service import CollectionError, add_item, get_valuation, list_collection, remove_item

router = APIRouter()


class CollectionItemIn(BaseModel):
    figure_id: str
    condition: Optional[str] = None
    photo_url: Optional[str] = None


@router.get("/collection")
async def get_collection(user: dict = Depends(get_current_user)):
    return {"items": list_collection(user["id"])}


@router.get("/collection/valuation")
async def collection_valuation(user: dict = Depends(get_current_user)):
    return get_valuation(user["id"])


@router.post("/collection", status_code=201)
async def post_collection(body: CollectionItemIn, user: dict = Depends(get_current_user)):
    try:
        return add_item(user["id"], body.figure_id, body.condition, body.photo_url)
    except CollectionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/collection/{figure_id}")
async def delete_collection_item(figure_id: str, user: dict = Depends(get_current_user)):
    if not remove_item(user["id"], figure_id):
        raise HTTPException(status_code=404, detail="item not in collection")
    return {"removed": figure_id}
