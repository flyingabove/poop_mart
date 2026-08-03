from fastapi import APIRouter, HTTPException
from backend.app.db.repos import CatalogRepo
from backend.app.pricing import service as pricing_service

router = APIRouter()


@router.get("/figures/{figure_id}/price-history")
async def price_history(figure_id: str):
    if not CatalogRepo.get_figure(figure_id):
        raise HTTPException(status_code=404, detail="figure not found")
    history = pricing_service.get_price_history(figure_id)
    return {"figure_id": figure_id, "history": history}
