from fastapi import APIRouter
import sys
import time

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "ok": True,
        "python": sys.version.split(" ")[0],
        "time": int(time.time()),
    }
