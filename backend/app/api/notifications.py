"""Notifications API — list, mark read."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, update

from backend.app.deps import CurrentUser, DBSession
from shared.models.notification import Notification
from shared.models.user import User

router = APIRouter()


@router.get("", response_model=list[dict])
async def list_notifications(
    session: DBSession,
    current_user: CurrentUser,
    limit: int = 50,
) -> list[dict]:
    """Return the most recent notifications for the authenticated user."""
    rows = (
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "url": n.url,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in rows
    ]


@router.post("/{notification_id}/read", response_model=dict)
async def mark_read(
    notification_id: int,
    session: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Mark a single notification as read."""
    await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await session.commit()
    return {"ok": True}


@router.post("/read-all", response_model=dict)
async def mark_all_read(
    session: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Mark all notifications for the current user as read."""
    await session.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await session.commit()
    return {"ok": True}
