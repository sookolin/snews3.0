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
from shared.security import decode_token, user_has_permission

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

    # Merge role-level permission overrides (configured in Users → Права ролей)
    # into the user's effective permissions so they are picked up by the guard.
    try:
        from shared.services.settings_service import SettingsService
        role_perms_cfg = await SettingsService(session).get("roles.permissions", {}) or {}
        role_key = user.role.value if hasattr(user.role, "value") else str(user.role)
        role_cfg = role_perms_cfg.get(role_key, {})
        # Stash the raw role config (including any per-city scoping) so
        # ``shared.security.resolve_city_scope``/``user_city_access`` can read
        # it without a second DB round-trip. Not persisted — session is not
        # committed, so the DB is untouched.
        user._role_perm_cfg = role_cfg  # type: ignore[attr-defined]
        if role_cfg:
            existing = dict(user.permissions or {})
            r_grant = set(role_cfg.get("grant") or [])
            r_deny  = set(role_cfg.get("deny") or [])
            u_grant = set(existing.get("grant") or [])
            u_deny  = set(existing.get("deny") or [])
            # User-level overrides always win; role-level fills the gaps.
            merged_grant = list((r_grant - u_deny) | u_grant)
            merged_deny  = list((r_deny  - u_grant) | u_deny)
            # Mutate in-place — session is not committed, so DB is untouched.
            user.permissions = {"grant": merged_grant, "deny": merged_deny}
    except Exception:  # noqa: BLE001 — never break auth because of this
        pass

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(
    permission: Permission,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Return a dependency that enforces ``permission`` for the current user."""

    async def _guard(user: CurrentUser) -> User:
        if not user_has_permission(user, permission):
            raise PermissionDeniedError(
                f"Missing permission: {permission.value}", code="permission_denied"
            )
        return user

    return _guard


def require_city_access(city_id: int | None, user: User) -> None:
    """Raise ``PermissionDeniedError`` if ``user`` has no access to ``city_id``.

    ``city_id`` of ``None`` (world/unassigned news) is always allowed.
    """
    from shared.security import user_can_access_city

    if not user_can_access_city(user, city_id):
        raise PermissionDeniedError(
            "Нет доступа к этому городу", code="city_access_denied"
        )


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
