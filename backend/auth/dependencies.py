"""Auth dependency — get_current_user from JWT Bearer token."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.security import decode_access_token
from backend.core.database import get_db
from backend.auth.models import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )
    return user


def require_plan(plan: str):
    """Decorator factory — enforces minimum plan tier."""
    tier_order = {"free": 0, "pro": 1, "enterprise": 2}

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if tier_order.get(current_user.plan_tier, 0) < tier_order.get(plan, 0):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This feature requires the '{plan}' plan or higher.",
            )
        return current_user

    return checker
