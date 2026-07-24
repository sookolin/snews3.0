"""User service — CRUD and lookups for users."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.exceptions import ConflictError, NotFoundError
from shared.models.user import User
from shared.schemas.user import UserCreate, UserUpdate
from shared.security import hash_password


class UserService:
    """Manage user accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_or_404(self, user_id: int) -> User:
        user = await self.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email.lower()))

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def list(self, offset: int = 0, limit: int = 50) -> tuple[list[User], int]:
        total = await self.session.scalar(select(func.count()).select_from(User)) or 0
        rows = (
            await self.session.scalars(
                select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
            )
        ).all()
        return list(rows), total

    async def create(self, payload: UserCreate) -> User:
        if await self.get_by_email(payload.email):
            raise ConflictError("Email already registered", code="email_exists")
        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
            language=payload.language,
            telegram_id=payload.telegram_id,
            hashed_password=hash_password(payload.password),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user_id: int, payload: UserUpdate) -> User:
        user = await self.get_or_404(user_id)
        data = payload.model_dump(exclude_unset=True)
        password = data.pop("password", None)
        for key, value in data.items():
            setattr(user, key, value)
        if password:
            user.hashed_password = hash_password(password)
        await self.session.flush()
        return user

    async def delete(self, user_id: int) -> None:
        user = await self.get_or_404(user_id)
        await self.session.delete(user)
        await self.session.flush()
