from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.service import AuthError, login, signup

router = APIRouter()


class SignupIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/signup", status_code=201)
async def auth_signup(body: SignupIn):
    try:
        return signup(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/auth/login")
async def auth_login(body: LoginIn):
    try:
        return login(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user
