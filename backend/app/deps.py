"""FastAPI dependencies: DB session, auth, rate limiting, permission guards."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_session
from shared.enums import Permission
from shared.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from shared.models.user import User
from shared.redis_client import get_redis
from shared.security import decode_token, has_permission

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session (delegates to the shared dependency)."""
    async for session in get_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DBSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """Resolve and validate the current authenticated user from the JWT."""
    if not token:
        raise AuthenticationError("Not authenticated", code="not_authenticated")
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")
    user = await session.get(User, int(user_id))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(
    permission: Permission,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Return a dependency that enforces ``permission`` for the current user."""

    async def _guard(user: CurrentUser) -> User:
        if not has_permission(user.role, permission):
            raise PermissionDeniedError(
                f"Missing permission: {permission.value}", code="permission_denied"
            )
        return user

    return _guard


async def rate_limiter(request: Request) -> None:
    """Simple fixed-window rate limiter backed by Redis (per-IP + path)."""
    client_ip = request.client.host if request.client else "unknown"
    window = 60
    limit = 300  # requests per window per ip
    key = f"ratelimit:{client_ip}:{int(time.time() // window)}"
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window)
        if count > limit:
            raise RateLimitError("Too many requests", code="rate_limited")
    except RateLimitError:
        raise
    except Exception:  # noqa: BLE001 - never fail requests if Redis is down
        return


def client_meta(
    request: Request,
    user_agent: Annotated[str | None, Header()] = None,
) -> dict[str, str | None]:
    """Extract IP + user agent for audit logging."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": user_agent,
    }


ClientMeta = Annotated[dict, Depends(client_meta)]
