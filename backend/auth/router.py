"""Auth domain — FastAPI router."""

import secrets
from fastapi import APIRouter, Depends, Response, Cookie, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import create_access_token, create_refresh_token, decode_access_token
from backend.core.redis import get_redis
from backend.auth.service import AuthService
from backend.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    RefreshRequest, PasswordResetRequest,
)
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.config import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    user = await svc.register(payload)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    user, access_token = await svc.login(payload)

    # Refresh token — issued as HttpOnly cookie
    refresh_value, refresh_id = create_refresh_token()
    redis = get_redis()
    await redis.setex(
        f"refresh:{refresh_id}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        f"{user.id}:{refresh_value}",
    )

    response.set_cookie(
        key="refresh_token",
        value=f"{refresh_id}:{refresh_value}",
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing.")

    try:
        refresh_id, refresh_value = refresh_token.split(":", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed refresh token.")

    redis = get_redis()
    stored = await redis.get(f"refresh:{refresh_id}")
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked.")

    stored_user_id, stored_value = stored.split(":", 1)
    if not secrets.compare_digest(stored_value, refresh_value):
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    # Rotate: invalidate the used refresh token and issue a new one.
    await redis.delete(f"refresh:{refresh_id}")

    svc = AuthService(db)
    user = await svc.get_user_by_id(stored_user_id)

    access_token = create_access_token(str(user.id), user.email)

    new_value, new_id = create_refresh_token()
    await redis.setex(
        f"refresh:{new_id}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        f"{user.id}:{new_value}",
    )
    response.set_cookie(
        key="refresh_token",
        value=f"{new_id}:{new_value}",
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(response: Response, refresh_token: str | None = Cookie(default=None)):
    response.delete_cookie("refresh_token")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
