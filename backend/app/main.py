import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config.settings import APP_TITLE, APP_VERSION, CORS_ORIGINS
from backend.app.db.database import init_db
from backend.app.db.seed import seed_if_empty
from backend.app.ingestion.news import run_ingestion_loop, DEFAULT_INTERVAL_SECONDS

from backend.app.api.health import router as health_router
from backend.app.api.feed import router as feed_router
from backend.app.api.figures import router as figures_router
from backend.app.api.pricing import router as pricing_router
from backend.app.api.guides import router as guides_router
from backend.app.api.search import router as search_router
from backend.app.api.auth import router as auth_router
from backend.app.api.collection import router as collection_router
from backend.app.api.wishlist import router as wishlist_router
from backend.app.api.follows import router as follows_router
from backend.app.api.notifications import router as notifications_router

_INDEX_HTML_PATH = Path(__file__).parent.parent.parent / "frontend" / "index.html"
_IMG_DIR = Path(__file__).parent.parent.parent / "frontend" / "img"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()

    ingestion_task = None
    if os.getenv("DISABLE_INGESTION") != "1":
        interval = int(os.getenv("INGEST_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)))
        ingestion_task = asyncio.create_task(run_ingestion_loop(interval))

    yield

    if ingestion_task:
        ingestion_task.cancel()


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(feed_router, prefix="/api")
app.include_router(figures_router, prefix="/api")
app.include_router(pricing_router, prefix="/api")
app.include_router(guides_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(collection_router, prefix="/api")
app.include_router(wishlist_router, prefix="/api")
app.include_router(follows_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")

_IMG_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/img", StaticFiles(directory=str(_IMG_DIR)), name="img")


@app.get("/", response_class=HTMLResponse)
async def index():
    return _INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/version")
async def version():
    return {"status": "ok", "backend": "python", "message": f"{APP_TITLE} running"}
