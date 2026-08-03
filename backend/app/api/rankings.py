from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.rankings.service import (
    RankingError,
    add_item,
    create_ranking,
    delete_ranking,
    get_ranking,
    list_rankings,
    remove_item,
)

router = APIRouter()


class RankingIn(BaseModel):
    title: str


class RankingItemIn(BaseModel):
    figure_id: str


@router.get("/rankings")
async def get_my_rankings(user: dict = Depends(get_current_user)):
    return {"rankings": list_rankings(user["id"])}


@router.post("/rankings", status_code=201)
async def post_ranking(body: RankingIn, user: dict = Depends(get_current_user)):
    try:
        return create_ranking(user["id"], body.title)
    except RankingError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/rankings/{ranking_id}")
async def get_ranking_detail(ranking_id: int):
    ranking = get_ranking(ranking_id)
    if not ranking:
        raise HTTPException(status_code=404, detail="ranking not found")
    return ranking


@router.delete("/rankings/{ranking_id}")
async def delete_ranking_route(ranking_id: int, user: dict = Depends(get_current_user)):
    if not delete_ranking(user["id"], ranking_id):
        raise HTTPException(status_code=404, detail="ranking not found")
    return {"id": ranking_id, "deleted": True}


@router.post("/rankings/{ranking_id}/items", status_code=201)
async def post_ranking_item(ranking_id: int, body: RankingItemIn, user: dict = Depends(get_current_user)):
    try:
        return add_item(user["id"], ranking_id, body.figure_id)
    except RankingError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/rankings/{ranking_id}/items/{figure_id}")
async def delete_ranking_item(ranking_id: int, figure_id: str, user: dict = Depends(get_current_user)):
    if not remove_item(user["id"], ranking_id, figure_id):
        raise HTTPException(status_code=404, detail="item not found")
    return {"ranking_id": ranking_id, "figure_id": figure_id, "removed": True}
