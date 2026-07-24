"""Pytest fixtures: in-memory SQLite DB + FastAPI test client with auth override."""

from __future__ import annotations

import os

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-please-change-1234567890")
os.environ.setdefault("APP_ENV", "development")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.database import Base  # noqa: E402
from shared.enums import UserRole  # noqa: E402
from shared.models.user import User  # noqa: E402
from shared.security import hash_password  # noqa: E402


@pytest_asyncio.fixture
async def engine():  # type: ignore[no-untyped-def]
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        email="admin@test.example",
        full_name="Admin",
        hashed_password=hash_password("password123"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def client(session_factory, admin_user) -> AsyncGenerator[AsyncClient, None]:
    from backend.app.deps import get_current_user, get_db
    from backend.app.main import app

    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _current_user() -> User:
        return admin_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _anyio_backend() -> str:
    return "asyncio"
