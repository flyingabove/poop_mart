from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.app.auth.dependencies import get_current_user, get_optional_user
from backend.app.db.repos import CatalogRepo
from backend.app.guides import service as guides_service

router = APIRouter()


class ContributionIn(BaseModel):
    figure_id: str
    technique_type: str  # weight | sound | box_code | seam
    claim_text: str
    weight_range_g: Optional[str] = None
    video_url: Optional[str] = None


class VoteIn(BaseModel):
    direction: str  # "up" or "down"


@router.get("/guides/{series_id}")
async def get_guide(series_id: str, user: Optional[dict] = Depends(get_optional_user)):
    if not CatalogRepo.get_series(series_id):
        raise HTTPException(status_code=404, detail="series not found")
    guide = guides_service.get_guide(series_id, user_id=user["id"] if user else None)
    if not guide:
        return {
            "series_id": series_id,
            "technique_summary": "Not enough contributions yet — be the first to add one.",
            "etiquette_note": (
                "Community folklore, not guaranteed. Some stores don't allow box handling — "
                "check before you shake, and always be gentle."
            ),
            "figure_signatures": [],
            "contributions": [],
        }
    return guide


@router.post("/guides/{series_id}/contributions", status_code=201)
async def add_contribution(series_id: str, body: ContributionIn):
    if not CatalogRepo.get_series(series_id):
        raise HTTPException(status_code=404, detail="series not found")
    if not CatalogRepo.get_figure(body.figure_id):
        raise HTTPException(status_code=404, detail="figure not found")
    try:
        result = guides_service.add_contribution(
            series_id=series_id,
            figure_id=body.figure_id,
            technique_type=body.technique_type,
            claim_text=body.claim_text,
            weight_range_g=body.weight_range_g,
            video_url=body.video_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.post("/guides/contributions/{contribution_id}/vote")
async def vote_contribution(contribution_id: int, body: VoteIn, user: dict = Depends(get_current_user)):
    try:
        return guides_service.vote_contribution(user["id"], contribution_id, body.direction)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
