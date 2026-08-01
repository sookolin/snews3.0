"""Notification router — sends in-app bell when user is online, falls back to
Telegram DM when they are away.

Presence is tracked via Redis key ``online:<user_id>`` with a 120-second TTL;
the frontend pings ``POST /profile/heartbeat`` every 60 s while the tab is open.

Usage::

    from shared.services.notify_router import notify_user

    await notify_user(
        session, user,
        type="news_pending",
        title="Новость на модерации",
        body="Пришла новость из Москвы.",
        url="/news/42",
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from shared.models.user import User


async def is_online(user_id: int) -> bool:
    """Return True if a heartbeat was received for this user in the last 2 min."""
    try:
        from shared.redis_client import get_redis

        redis = get_redis()
        return bool(await redis.exists(f"online:{user_id}"))
    except Exception:  # noqa: BLE001
        return False


async def notify_user(
    session: AsyncSession,
    user: "User",
    *,
    type: str,
    title: str,
    body: str | None = None,
    url: str | None = None,
    force_dm: bool = False,
) -> None:
    """Create an in-app notification and optionally send a Telegram DM.

    Logic:
    - Always write the in-app Notification row (bell icon).
    - If the user is offline (no recent heartbeat) AND has a linked telegram_id
      AND the user's inapp prefs allow the notification type, also send a TG DM.
    - Pass ``force_dm=True`` to send a DM regardless of presence (used for
      critical events like account_deactivated).
    """
    from shared.models.notification import Notification

    # 1. In-app notification — always created.
    notif = Notification(
        user_id=user.id,
        type=type,
        title=title,
        body=body,
        url=url,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    session.add(notif)
    await session.flush()

    # 1b. Web Push mirror — deliver the very same event to the browser/PWA so
    # push and the in-app bell fire together. Best-effort: a push failure must
    # never break the bell. ``PushService.notify`` itself checks the user's push
    # prefs, so a user who disabled this event for push simply gets nothing.
    try:
        from shared.services.push_service import PushService

        await PushService(session).notify(
            user, event=type, title=title, body=body or "", url=url or "/"
        )
    except Exception:  # noqa: BLE001
        pass

    # 2. Telegram DM — only when the user is away or forced.
    if not user.telegram_id:
        return

    # Check inapp prefs: if the user explicitly disabled this type, skip DM too.
    inapp_prefs: dict = ((user.notify_prefs or {}).get("inapp") or {})
    if inapp_prefs.get(type) is False:
        return

    online = await is_online(user.id)
    if online and not force_dm:
        return

    # Build DM text.
    lines = [f"🔔 <b>{title}</b>"]
    if body:
        lines.append(body)
    if url:
        from shared.config import settings

        panel = settings.admin_panel_url.rstrip("/")
        if url.startswith("/"):
            lines.append(f"<a href=\"{panel}{url}\">Открыть в панели</a>")
    text = "\n".join(lines)

    try:
        from shared.services.bot_notify import BotNotifyService

        svc = BotNotifyService(session)
        await svc._send(int(user.telegram_id), text)
    except Exception:  # noqa: BLE001
        pass
