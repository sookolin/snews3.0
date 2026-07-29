"""Personal cabinet: own profile, stats, notification prefs, push devices.

Super admins may open any user's cabinet by passing ``user_id``; everyone else
only ever sees their own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
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
    """Self-edit: name and language only (email/role require user:manage)."""

    full_name: str | None = None
    language: str | None = None


class NotifyPrefsIn(BaseModel):
    """Whole prefs object, merged over the stored one."""

    push: dict | None = None
    bot: dict | None = None


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
    """Update own profile (name, language). Super admins can edit others."""
    user = await _target(session, actor, user_id)
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(user, key, value)
    await session.flush()
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
    """Register this device for Web Push (replaces a same-endpoint entry)."""
    devices = [
        d for d in (actor.push_subscriptions or []) if d.get("endpoint") != payload.endpoint
    ]
    devices.append({"endpoint": payload.endpoint, "keys": payload.keys})
    actor.push_subscriptions = devices
    await session.commit()
    return Message(detail="Устройство подписано на уведомления")


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
