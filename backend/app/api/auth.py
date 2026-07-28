"""Authentication endpoints: login, refresh, 2FA."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
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


class TelegramLoginRequest(BaseModel):
    """Payload from the Telegram Login Widget."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class YandexLoginRequest(BaseModel):
    """OAuth access token obtained from Yandex."""

    access_token: str


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

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    return TokenPair(
        access_token=create_access_token(user.id, {"role": user.role.value}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/yandex", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login_yandex(payload: YandexLoginRequest, session: DBSession) -> TokenPair:
    """Authenticate via a Yandex OAuth access token.

    The token is validated against Yandex's ``login.info`` endpoint; the
    resulting Yandex account must be linked to a user (``users.yandex_id``) or
    match the user's email.
    """
    import httpx
    from sqlalchemy import select

    from shared.models.user import User as UserModel

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://login.yandex.ru/info",
                params={"format": "json"},
                headers={"Authorization": f"OAuth {payload.access_token}"},
            )
        if resp.status_code != 200:
            raise AuthenticationError("Яндекс отклонил токен", code="yandex_invalid_token")
        info = resp.json()
    except AuthenticationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError(
            f"Не удалось проверить токен Яндекса: {exc}", code="yandex_unreachable"
        ) from exc

    yandex_id = str(info.get("id") or "")
    email = (info.get("default_email") or "").lower()
    if not yandex_id:
        raise AuthenticationError("Яндекс не вернул идентификатор", code="yandex_no_id")

    user = await session.scalar(select(UserModel).where(UserModel.yandex_id == yandex_id))
    if user is None and email:
        user = await UserService(session).get_by_email(email)
        if user is not None:
            # Link the account on first successful login.
            user.yandex_id = yandex_id
    if user is None or not user.is_active:
        raise AuthenticationError(
            "Этот Яндекс-аккаунт не привязан к пользователю", code="yandex_not_linked"
        )

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    return TokenPair(
        access_token=create_access_token(user.id, {"role": user.role.value}),
        refresh_token=create_refresh_token(user.id),
    )


class VKLoginRequest(BaseModel):
    """VK access token (implicit flow) plus the optional email VK returned."""

    access_token: str
    email: str | None = None
    user_id: int | None = None


@router.post("/vk", response_model=TokenPair, dependencies=[Depends(rate_limiter)])
async def login_vk(payload: VKLoginRequest, session: DBSession) -> TokenPair:
    """Authenticate via a VK OAuth access token.

    The token is validated with ``users.get``; the resulting VK id must be
    linked to a user (``users.vk_id``) or match the user's email.
    """
    import httpx
    from sqlalchemy import select

    from shared.models.user import User as UserModel

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.vk.com/method/users.get",
                params={"access_token": payload.access_token, "v": "5.199"},
            )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise AuthenticationError(
            f"Не удалось проверить токен VK: {exc}", code="vk_unreachable"
        ) from exc

    if "error" in data:
        raise AuthenticationError("VK отклонил токен", code="vk_invalid_token")
    items = data.get("response") or []
    vk_id = str(items[0].get("id")) if items else (str(payload.user_id) if payload.user_id else "")
    if not vk_id:
        raise AuthenticationError("VK не вернул идентификатор", code="vk_no_id")

    user = await session.scalar(select(UserModel).where(UserModel.vk_id == vk_id))
    if user is None and payload.email:
        user = await UserService(session).get_by_email(payload.email.lower())
        if user is not None:
            user.vk_id = vk_id
    if user is None or not user.is_active:
        raise AuthenticationError(
            "Этот VK-аккаунт не привязан к пользователю", code="vk_not_linked"
        )

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
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
