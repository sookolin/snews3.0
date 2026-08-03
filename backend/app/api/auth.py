"""Authentication endpoints: login, refresh, 2FA."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

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


async def _after_login(session, user, request: Request | None = None) -> None:
    """Stamp the login time and DM the user if they asked to be told."""
    import contextlib

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    # A dead bot token or a blocked chat must never break signing in.
    with contextlib.suppress(Exception):
        from shared.services.bot_notify import BotNotifyService

        ip = request.client.host if request is not None and request.client else None
        await BotNotifyService(session).notify_login(user, ip=ip)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login(payload: LoginRequest, session: DBSession, request: Request) -> TokenPair:
    """Authenticate a user and return an access/refresh token pair."""
    service = UserService(session)
    user = await service.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Invalid credentials", code="invalid_credentials")
    if not user.is_active:
        raise AuthenticationError("User is inactive", code="user_inactive")
    if user.is_banned:
        raise AuthenticationError("Account is banned", code="user_banned")

    if user.is_2fa_enabled:
        if not payload.totp_code:
            raise AuthenticationError("2FA code required", code="2fa_required")
        if not user.totp_secret or not verify_totp(user.totp_secret, payload.totp_code):
            raise AuthenticationError("Invalid 2FA code", code="2fa_invalid")

    await _after_login(session, user, request)
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


class TelegramLoginRequest(BaseModel):
    """Payload from the Telegram Login Widget."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


@router.post("/telegram", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login_telegram(payload: TelegramLoginRequest, session: DBSession) -> TokenPair:
    """Authenticate via the Telegram Login Widget.

    The widget signature is verified with HMAC-SHA256 using the bot token, as
    described in the Telegram documentation. The Telegram account must already
    be linked to a user (``users.telegram_id``).
    """
    import hashlib
    import hmac
    import time

    from shared.config import settings

    if not settings.telegram_bot_token:
        raise AuthenticationError("Telegram login не настроен", code="telegram_not_configured")

    data = payload.model_dump(exclude_none=True)
    received_hash = data.pop("hash")
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise AuthenticationError("Неверная подпись Telegram", code="telegram_bad_signature")
    if time.time() - payload.auth_date > 86400:
        raise AuthenticationError("Данные Telegram устарели", code="telegram_expired")

    service = UserService(session)
    user = await service.get_by_telegram_id(payload.id)
    if user is None or not user.is_active:
        raise AuthenticationError(
            "Этот Telegram-аккаунт не привязан к пользователю", code="telegram_not_linked"
        )

    # Keep the avatar in sync each time the user logs in via Telegram.
    if payload.photo_url:
        user.photo_url = payload.photo_url

    await _after_login(session, user)
    return TokenPair(
        access_token=create_access_token(user.id, {"role": user.role.value}),
        refresh_token=create_refresh_token(user.id),
    )



class WebAppLoginRequest(BaseModel):
    """Raw ``initData`` string from a Telegram Mini App (WebApp)."""

    init_data: str


@router.post("/telegram/webapp", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login_telegram_webapp(payload: WebAppLoginRequest, session: DBSession) -> TokenPair:
    """Authenticate a Telegram Mini App session from its signed ``initData``.

    Lets the admin mini app (opened from the bot via /start) come up already
    authenticated as the Telegram account interacting with the bot. The account
    must be linked to a user (``users.telegram_id``).
    """
    from shared.config import settings
    from shared.services.telegram_webapp import validate_init_data

    if not settings.telegram_bot_token:
        raise AuthenticationError("Telegram login не настроен", code="telegram_not_configured")

    tg_user = validate_init_data(payload.init_data, settings.telegram_bot_token)
    if not tg_user or not tg_user.get("id"):
        raise AuthenticationError("Неверные данные Telegram", code="telegram_bad_signature")

    service = UserService(session)
    user = await service.get_by_telegram_id(int(tg_user["id"]))
    if user is None or not user.is_active:
        raise AuthenticationError(
            "Этот Telegram-аккаунт не привязан к пользователю", code="telegram_not_linked"
        )

    if tg_user.get("photo_url"):
        user.photo_url = tg_user["photo_url"]

    await _after_login(session, user)
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
