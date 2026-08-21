"""
JWT utilities — RS256 asymmetric signing.
Access token: 15 min | Refresh token: 7 days (stored HttpOnly cookie).
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, JOSEError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import secrets

from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ───────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, email: str) -> str:
    expire = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": expire,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, settings.PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Returns (token_value, token_id). Store hashed token_id in DB/Redis."""
    token_id = secrets.token_urlsafe(32)
    token_value = secrets.token_urlsafe(64)
    return token_value, token_id


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        return payload
    except (JWTError, JOSEError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
