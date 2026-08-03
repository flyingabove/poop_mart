from fastapi import APIRouter, HTTPException
from typing import Optional
from backend.app.db.repos import CatalogRepo
from backend.app.pricing import service as pricing_service

router = APIRouter()


@router.get("/series")
async def list_series():
    return {"series": CatalogRepo.list_series()}


@router.get("/series/{series_id}")
async def get_series(series_id: str):
    series = CatalogRepo.get_series(series_id)
    if not series:
        raise HTTPException(status_code=404, detail="series not found")
    figures = CatalogRepo.list_figures(series_id=series_id)
    return {"series": series, "figures": figures}


@router.get("/figures")
async def list_figures(series_id: Optional[str] = None):
    return {"figures": CatalogRepo.list_figures(series_id=series_id)}


@router.get("/figures/{figure_id}")
async def get_figure(figure_id: str):
    figure = CatalogRepo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="figure not found")
    return {
        "figure": figure,
        "current_price": pricing_service.get_current_price(figure_id),
    }
