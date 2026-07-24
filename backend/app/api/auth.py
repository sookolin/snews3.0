"""Authentication endpoints: login, refresh, 2FA."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.app.deps import CurrentUser, DBSession, rate_limiter
from shared.exceptions import AuthenticationError
from shared.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    TwoFactorSetup,
    TwoFactorVerify,
)
from shared.schemas.user import UserOut
from shared.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from shared.services.user_service import UserService

router = APIRouter()


@router.post("/login", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login(payload: LoginRequest, session: DBSession) -> TokenPair:
    """Authenticate a user and return an access/refresh token pair."""
    service = UserService(session)
    user = await service.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Invalid credentials", code="invalid_credentials")
    if not user.is_active:
        raise AuthenticationError("User is inactive", code="user_inactive")

    if user.is_2fa_enabled:
        if not payload.totp_code:
            raise AuthenticationError("2FA code required", code="2fa_required")
        if not user.totp_secret or not verify_totp(user.totp_secret, payload.totp_code):
            raise AuthenticationError("Invalid 2FA code", code="2fa_invalid")

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()

    return TokenPair(
        access_token=create_access_token(user.id, {"role": user.role.value}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: DBSession) -> TokenPair:
    """Exchange a valid refresh token for a new token pair."""
    data = decode_token(payload.refresh_token, expected_type="refresh")
    user_id = int(data["sub"])
    service = UserService(session)
    user = await service.get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    return TokenPair(
        access_token=create_access_token(user.id, {"role": user.role.value}),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    """Return the current authenticated user."""
    return UserOut.model_validate(user)


@router.post("/2fa/setup", response_model=TwoFactorSetup)
async def setup_2fa(user: CurrentUser, session: DBSession) -> TwoFactorSetup:
    """Generate a TOTP secret for the current user (not yet enabled)."""
    secret = generate_totp_secret()
    user.totp_secret = secret
    await session.flush()
    return TwoFactorSetup(
        secret=secret,
        provisioning_uri=totp_provisioning_uri(secret, user.email),
    )


@router.post("/2fa/enable", response_model=UserOut)
async def enable_2fa(payload: TwoFactorVerify, user: CurrentUser, session: DBSession) -> UserOut:
    """Verify a TOTP code and enable 2FA for the current user."""
    if not user.totp_secret or not verify_totp(user.totp_secret, payload.totp_code):
        raise AuthenticationError("Invalid 2FA code", code="2fa_invalid")
    user.is_2fa_enabled = True
    await session.flush()
    return UserOut.model_validate(user)


@router.post("/2fa/disable", response_model=UserOut)
async def disable_2fa(user: CurrentUser, session: DBSession) -> UserOut:
    """Disable 2FA for the current user."""
    user.is_2fa_enabled = False
    user.totp_secret = None
    await session.flush()
    return UserOut.model_validate(user)
