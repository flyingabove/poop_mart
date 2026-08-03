"""FastAPI dependency for routes that require a logged-in user."""
import jwt
from fastapi import Header, HTTPException

from backend.app.auth.security import decode_access_token
from backend.app.auth.service import get_user


async def get_current_user(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")

    user = get_user(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user
