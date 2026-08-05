"""Personal cabinet: own profile, stats, notification prefs, push devices.

Super admins may open any user's cabinet by passing ``user_id``; everyone else
only ever sees their own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend.app.deps import CurrentUser, DBSession
from shared.enums import NewsStatus, UserRole
from shared.models.news import News
from shared.models.user import User
from shared.schemas.common import Message
from shared.schemas.user import UserOut
from shared.services.push_service import PushService

router = APIRouter()


class ProfileStats(BaseModel):
    """Activity counters for the cabinet dashboard."""

    moderated_total: int = 0
    approved: int = 0
    rejected: int = 0
    published: int = 0
    edited: int = 0
    last_7_days: list[dict] = Field(default_factory=list)


class ProfileOut(BaseModel):
    user: UserOut
    stats: ProfileStats
    notify_prefs: dict = Field(default_factory=dict)
    push_devices: int = 0
    is_self: bool = True


class ProfileUpdateIn(BaseModel):
    """Self-edit: basic info. Admins can change email/password/2FA too."""

    full_name: str | None = None
    language: str | None = None
    email: str | None = None
    password: str | None = None
    # Telegram link — users manage their own binding here.
    telegram_id: int | None = None
    telegram_username: str | None = None


class NotifyPrefsIn(BaseModel):
    """Whole prefs object, merged over the stored one."""

    push:  dict | None = None
    bot:   dict | None = None
    inapp: dict | None = None


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict


async def _target(session, actor: User, user_id: int | None) -> User:
    """Resolve whose cabinet is being opened, enforcing super-admin access."""
    if user_id is None or user_id == actor.id:
        return actor
    if actor.role != UserRole.SUPER_ADMIN:
        raise HTTPException(403, "Доступ только у супер-администратора")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    return user


async def _stats(session, user: User) -> ProfileStats:
    """Count what this user moderated, plus a 7-day activity series."""
    rows = (
        await session.execute(
            select(News.status, func.count())
            .where(News.moderated_by == user.id)
            .group_by(News.status)
        )
    ).all()
    by_status = {status: count for status, count in rows}

    def n(*statuses: NewsStatus) -> int:
        return sum(int(by_status.get(s, 0)) for s in statuses)

    edited = int(
        (
            await session.execute(
                select(func.count())
                .select_from(News)
                .where(News.moderated_by == user.id, News.is_edited.is_(True))
            )
        ).scalar()
        or 0
    )

    # News has no dedicated moderated_at column; updated_at is the closest
    # marker of when this user last acted on the item.
    since = datetime.now(timezone.utc) - timedelta(days=6)
    daily = (
        await session.execute(
            select(func.date(News.updated_at), func.count())
            .where(News.moderated_by == user.id, News.updated_at >= since)
            .group_by(func.date(News.updated_at))
        )
    ).all()
    counts = {str(day): int(count) for day, count in daily}
    series = []
    for offset in range(6, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date()
        series.append({"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)})

    return ProfileStats(
        moderated_total=sum(int(v) for v in by_status.values()),
        approved=n(NewsStatus.APPROVED, NewsStatus.SCHEDULED, NewsStatus.PUBLISHED),
        rejected=n(NewsStatus.REJECTED),
        published=n(NewsStatus.PUBLISHED),
        edited=edited,
        last_7_days=series,
    )


@router.get("", response_model=ProfileOut)
async def get_profile(
    session: DBSession,
    actor: CurrentUser,
    user_id: int | None = None,
) -> ProfileOut:
    """Cabinet payload: profile, activity stats and notification settings."""
    user = await _target(session, actor, user_id)
    return ProfileOut(
        user=UserOut.model_validate(user),
        stats=await _stats(session, user),
        notify_prefs=user.notify_prefs or {},
        push_devices=len(user.push_subscriptions or []),
        is_self=user.id == actor.id,
    )


@router.patch("", response_model=UserOut)
async def update_profile(
    payload: ProfileUpdateIn,
    session: DBSession,
    actor: CurrentUser,
    user_id: int | None = None,
) -> UserOut:
    """Update own profile. Super admins can edit others."""
    from datetime import datetime, timezone

    from shared.models.notification import Notification
    from shared.security import hash_password
    from shared.services.bot_notify import BotNotifyService

    user = await _target(session, actor, user_id)
    # exclude_unset so unmentioned fields are not touched; but explicit null IS
    # allowed for social IDs so users can unlink Telegram/Yandex/VK.
    data = payload.model_dump(exclude_unset=True)

    # email and password changes are sensitive — only the user themselves or super admins
    for sensitive in ("email", "password"):
        actor_role = actor.role.value if hasattr(actor.role, "value") else actor.role
        if sensitive in data and user.id != actor.id and actor_role != "super_admin":
            from fastapi import HTTPException
            raise HTTPException(403, "Только супер-администратор может менять эти поля у других")

    if "password" in data:
        user.hashed_password = hash_password(data.pop("password"))

    # Track meaningful changes for notifications before applying them.
    changed_fields: list[str] = []
    for key in ("full_name", "email", "language", "telegram_id", "telegram_username"):
        if key in data and getattr(user, key) != data[key]:
            changed_fields.append(key)

    for key, value in data.items():
        setattr(user, key, value)
    await session.flush()

    # Notify the user (in-app) when their own profile was changed by someone else.
    if changed_fields and user.id != actor.id:
        field_labels = {
            "full_name": "имя",
            "email": "email",
            "language": "язык",
            "telegram_id": "Telegram ID",
            "telegram_username": "Telegram ник",
        }
        changed_str = ", ".join(field_labels.get(f, f) for f in changed_fields)
        notif = Notification(
            user_id=user.id,
            type="profile_updated",
            title="Профиль обновлён администратором",
            body=f"Изменено: {changed_str}.",
            url="/profile",
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(notif)
        await session.flush()

        # Mirror to Web Push (best-effort; respects the user's push prefs).
        try:
            await PushService(session).notify(
                user,
                event="profile_updated",
                title="Профиль обновлён администратором",
                body=f"Изменено: {changed_str}.",
                url="/profile",
            )
        except Exception:  # noqa: BLE001
            pass

        # Send a Telegram DM if the user has a linked account (best-effort).
        if user.telegram_id:
            bot = BotNotifyService(session)
            await bot._send(
                user.telegram_id,
                f"✏️ <b>Ваш профиль обновлён</b>\nИзменено: {changed_str}.\n"
                f"Если вы не запрашивали это — обратитесь к администратору.",
            )

    await session.commit()
    return UserOut.model_validate(user)


@router.put("/notifications", response_model=Message)
async def set_notifications(
    payload: NotifyPrefsIn,
    session: DBSession,
    actor: CurrentUser,
    user_id: int | None = None,
) -> Message:
    """Merge the submitted notification groups into the stored prefs."""
    user = await _target(session, actor, user_id)
    prefs = dict(user.notify_prefs or {})
    for group, value in payload.model_dump(exclude_none=True).items():
        if isinstance(value, dict):
            prefs[group] = {**dict(prefs.get(group) or {}), **value}
    user.notify_prefs = prefs
    await session.flush()
    await session.commit()
    return Message(detail="Настройки уведомлений сохранены")


@router.get("/push/key", response_model=dict)
async def push_public_key(session: DBSession, actor: CurrentUser) -> dict:
    """VAPID public key the browser needs to create a push subscription."""
    return {"key": await PushService(session).public_key()}


@router.post("/push", response_model=Message)
async def subscribe_push(
    payload: PushSubscriptionIn,
    session: DBSession,
    actor: CurrentUser,
) -> Message:
    """Register this device for Web Push (replaces a same-endpoint entry).

    Subscribing a device also opts the user into the default push events when
    they have no push preferences yet. Without this, a freshly subscribed
    device would receive nothing — ``PushService.notify`` only sends events the
    user has explicitly enabled, so registering alone was not enough.
    """
    devices = [
        d for d in (actor.push_subscriptions or []) if d.get("endpoint") != payload.endpoint
    ]
    devices.append({"endpoint": payload.endpoint, "keys": payload.keys})
    actor.push_subscriptions = devices

    prefs = dict(actor.notify_prefs or {})
    if not prefs.get("push"):
        # Sensible defaults: the moderation-relevant events plus the account
        # events also shown by the in-app bell, so push mirrors the bell out of
        # the box. The user can still fine-tune these checkboxes afterwards.
        prefs["push"] = {
            "news_pending": True,
            "news_published": True,
            "news_failed": True,
            "role_changed": True,
            "profile_updated": True,
            "password_changed": True,
            "account_deactivated": True,
            "account_activated": True,
            "2fa_reset": True,
        }
        actor.notify_prefs = prefs

    await session.commit()
    return Message(detail="Устройство подписано на уведомления")


@router.post("/push/test", response_model=Message)
async def test_push(session: DBSession, actor: CurrentUser) -> Message:
    """Send a test push to this user's devices, bypassing event prefs.

    Returns how many devices accepted it so misconfiguration (no device, dead
    subscription, missing HTTPS/VAPID) is visible instead of failing silently.
    """
    devices = list(actor.push_subscriptions or [])
    if not devices:
        raise HTTPException(400, "Нет подписанных устройств. Включите тумблер push выше.")
    service = PushService(session)
    sent = await service.send_test(
        actor,
        "Тест уведомления",
        "Если вы видите это — push работает.",
    )
    if sent == 0:
        reason = service.last_error or ""
        # A corrupt VAPID key can never deliver — point the user at the reset.
        if "corrupt" in reason or "not set" in reason:
            raise HTTPException(
                400,
                "VAPID-ключ повреждён или отсутствует. Нажмите «Пересоздать ключи», "
                "затем заново включите push и повторите проверку.",
            )
        detail = "Не удалось доставить push."
        if reason:
            detail += f" Причина: {reason}"
        raise HTTPException(400, detail)
    return Message(detail=f"Отправлено на устройств: {sent}")


@router.post("/push/reset", response_model=Message)
async def reset_push_keys(session: DBSession, actor: CurrentUser) -> Message:
    """Regenerate the server VAPID key pair and clear all stale subscriptions.

    Recovers from a corrupt/mismatched VAPID key. All existing browser
    subscriptions were made against the old public key and become invalid, so
    every user's stored subscriptions are cleared; users must re-enable push.
    Restricted to super admins since it affects every user.
    """
    if actor.role != UserRole.SUPER_ADMIN:
        raise HTTPException(403, "Только супер-администратор может пересоздать ключи push")
    await PushService(session).reset_keys()
    await session.execute(
        User.__table__.update().values(push_subscriptions=[])
    )
    await session.commit()
    return Message(detail="Ключи push пересозданы. Включите push заново на каждом устройстве.")


@router.delete("/push", response_model=Message)
async def unsubscribe_push(
    session: DBSession,
    actor: CurrentUser,
    endpoint: str | None = None,
) -> Message:
    """Drop one device (by endpoint) or every device when none is given."""
    if endpoint:
        actor.push_subscriptions = [
            d for d in (actor.push_subscriptions or []) if d.get("endpoint") != endpoint
        ]
    else:
        actor.push_subscriptions = []
    await session.commit()
    return Message(detail="Подписка отключена")


@router.post("/heartbeat", response_model=dict)
async def heartbeat(actor: CurrentUser) -> dict:
    """Ping presence: user is online. 2-min TTL key in Redis."""
    from shared.redis_client import get_redis

    redis = get_redis()
    key = f"online:{actor.id}"
    await redis.set(key, "1", ex=120)
    return {"ok": True}


@router.post("/photo", response_model=UserOut)
async def upload_photo(
    session: DBSession,
    actor: CurrentUser,
    user_id: int | None = None,
    file: UploadFile = File(...),
) -> UserOut:
    """Upload a profile avatar. Stores the file under /data/media/avatars/ and
    sets ``photo_url`` on the target user.  Super admins may pass ``user_id``."""
    import os
    import uuid

    from shared.config import settings

    user = await _target(session, actor, user_id)

    # Validate MIME type — only images allowed.
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Допустимы только изображения (jpeg, png, webp, gif)")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:  # 5 MB cap
        raise HTTPException(400, "Файл слишком большой (максимум 5 МБ)")

    subdir = os.path.join(settings.media_root, "avatars")
    os.makedirs(subdir, exist_ok=True)

    ext = os.path.splitext(file.filename or "avatar.jpg")[1].lower() or ".jpg"
    filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(subdir, filename)

    with open(filepath, "wb") as fh:
        fh.write(contents)

    user.photo_url = f"/media/avatars/{filename}"
    await session.flush()
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
