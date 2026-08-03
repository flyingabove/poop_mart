from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth.dependencies import get_current_user, get_optional_user
from backend.app.reviews.service import (
    ReviewError,
    add_or_update_review,
    get_user_review,
    list_reviews,
    remove_review,
    vote_review,
)

router = APIRouter()


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = None


class ReviewVoteIn(BaseModel):
    direction: str  # "helpful" or "unhelpful"


@router.get("/figures/{figure_id}/reviews")
async def get_reviews(figure_id: str, user: Optional[dict] = Depends(get_optional_user)):
    data = list_reviews(figure_id, user_id=user["id"] if user else None)
    data["my_review"] = get_user_review(user["id"], figure_id) if user else None
    return data


@router.post("/figures/{figure_id}/reviews", status_code=201)
async def post_review(figure_id: str, body: ReviewIn, user: dict = Depends(get_current_user)):
    try:
        return add_or_update_review(user["id"], figure_id, body.rating, body.text)
    except ReviewError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/figures/{figure_id}/reviews")
async def delete_review(figure_id: str, user: dict = Depends(get_current_user)):
    if not remove_review(user["id"], figure_id):
        raise HTTPException(status_code=404, detail="review not found")
    return {"figure_id": figure_id, "removed": True}


@router.post("/reviews/{review_id}/vote")
async def post_review_vote(review_id: int, body: ReviewVoteIn, user: dict = Depends(get_current_user)):
    try:
        return vote_review(user["id"], review_id, body.direction)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
