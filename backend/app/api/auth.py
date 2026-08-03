from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.rate_limit import RateLimiter
from backend.app.auth.service import AuthError, login, signup
from backend.app.badges.service import get_badges

router = APIRouter()

# 5 attempts / 5 minutes per key (per module docstring: in-process, single
# Railway instance -- see rate_limit.py for why that's a real limiter here,
# not a stub).
_login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
_signup_limiter = RateLimiter(max_attempts=10, window_seconds=3600)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class SignupIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/signup", status_code=201)
async def auth_signup(body: SignupIn, request: Request):
    if not _signup_limiter.check(f"ip:{_client_ip(request)}"):
        raise HTTPException(status_code=429, detail="too many signup attempts, try again later")
    try:
        return signup(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/auth/login")
async def auth_login(body: LoginIn, request: Request):
    ip_key = f"ip:{_client_ip(request)}"
    email_key = f"email:{body.email.strip().lower()}"
    # Both checked unconditionally (not short-circuited) -- an IP-level
    # attacker rotating target emails is still capped per-IP, and a
    # distributed attack targeting one account is still capped per-email.
    ip_ok = _login_limiter.check(ip_key)
    email_ok = _login_limiter.check(email_key)
    if not ip_ok or not email_ok:
        raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    try:
        result = login(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Successful login clears both counters so a legitimate user who
    # mistypes their password a few times isn't locked out afterward.
    _login_limiter.reset(ip_key)
    _login_limiter.reset(email_key)
    return result


@router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {**user, "badges": get_badges(user["id"])}
