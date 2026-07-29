"""Direct-message notifications sent by the bot to panel users.

Two kinds, both opt-in per user in the personal cabinet
(``notify_prefs["bot"]``): a login alert and a daily statistics digest. Users
without a linked ``telegram_id`` are skipped — there is nowhere to write.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.enums import NewsStatus
from shared.models.news import News
from shared.models.user import User
from shared.services.settings_service import SettingsService

logger = structlog.get_logger(__name__)


class BotNotifyService:
    """Sends the cabinet-configured DMs through the Telegram bot token."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _wants(user: User, key: str) -> bool:
        return bool(((user.notify_prefs or {}).get("bot") or {}).get(key))

    async def _send(self, chat_id: int, text: str) -> bool:
        """One-off DM; a blocked or never-started chat is not an error."""
        if not settings.telegram_bot_token:
            return False
        from aiogram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("bot_dm_failed", chat_id=chat_id, error=str(exc))
            return False
        finally:
            await bot.session.close()

    async def notify_login(self, user: User, ip: str | None = None) -> bool:
        """Tell the user their account was just used to sign in."""
        if not user.telegram_id or not self._wants(user, "login"):
            return False
        offset = int(await SettingsService(self.session).get("ui.timezone_offset_hours", 3))
        when = (datetime.now(timezone.utc) + timedelta(hours=offset)).strftime("%d.%m.%Y %H:%M")
        lines = [
            "🔐 <b>Вход в панель SNEWS</b>",
            f"Аккаунт: {user.email}",
            f"Время: {when}",
        ]
        if ip:
            lines.append(f"IP: {ip}")
        lines.append("")
        lines.append("Если это были не вы — смените пароль и включите 2FA.")
        return await self._send(user.telegram_id, "\n".join(lines))

    async def _daily_text(self, user: User, offset: int) -> str:
        """Digest for the last 24 hours: overall flow plus this user's own work."""
        since = datetime.now(timezone.utc) - timedelta(days=1)
        rows = (
            await self.session.execute(
                select(News.status, func.count())
                .where(News.created_at >= since)
                .group_by(News.status)
            )
        ).all()
        by_status = {status: int(count) for status, count in rows}
        mine = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(News)
                    .where(News.moderated_by == user.id, News.updated_at >= since)
                )
            ).scalar()
            or 0
        )
        day = (datetime.now(timezone.utc) + timedelta(hours=offset)).strftime("%d.%m.%Y")
        return "\n".join(
            [
                f"📊 <b>Статистика за сутки</b> ({day})",
                "",
                f"Найдено новостей: {sum(by_status.values())}",
                f"На модерации: {by_status.get(NewsStatus.PENDING, 0)}",
                f"Опубликовано: {by_status.get(NewsStatus.PUBLISHED, 0)}",
                f"Отклонено: {by_status.get(NewsStatus.REJECTED, 0)}",
                f"Ошибок: {by_status.get(NewsStatus.FAILED, 0)}",
                "",
                f"Обработано вами: {mine}",
            ]
        )

    async def send_daily_digests(self, hour: int | None = None) -> int:
        """Send digests to users whose configured hour matches ``hour``.

        ``hour`` is in display timezone; when omitted the current hour is used,
        which is how the hourly Celery beat task calls it.
        """
        offset = int(await SettingsService(self.session).get("ui.timezone_offset_hours", 3))
        now_local = datetime.now(timezone.utc) + timedelta(hours=offset)
        target = now_local.hour if hour is None else hour

        users = (
            await self.session.scalars(
                select(User).where(User.is_active.is_(True), User.telegram_id.is_not(None))
            )
        ).all()
        sent = 0
        for user in users:
            if not self._wants(user, "daily_stats"):
                continue
            prefs = (user.notify_prefs or {}).get("bot") or {}
            configured = str(prefs.get("daily_time") or "09:00")
            try:
                wanted = int(configured.split(":")[0])
            except ValueError:
                wanted = 9
            if wanted != target:
                continue
            text = await self._daily_text(user, offset)
            if await self._send(int(user.telegram_id), text):
                sent += 1
        return sent
