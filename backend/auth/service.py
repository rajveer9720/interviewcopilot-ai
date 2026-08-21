"""Auth domain — business logic service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from backend.auth.models import User
from backend.auth.schemas import RegisterRequest, LoginRequest
from backend.core.security import hash_password, verify_password, create_access_token
from backend.config import settings


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: RegisterRequest) -> User:
        # Check for existing user
        existing = await self.db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def login(self, payload: LoginRequest) -> tuple[User, str]:
        result = await self.db.execute(
            select(User).where(User.email == payload.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled.",
            )

        token = create_access_token(str(user.id), user.email)
        return user, token

    async def get_user_by_id(self, user_id: str) -> User:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return user
