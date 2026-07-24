"""Telegram admin service — topic creation & moderation card delivery.

Uses a short-lived aiogram Bot instance for administrative actions initiated by
the backend/workers (creating a city's forum topic, sending the moderation card
with inline buttons to the city's topic in the moderation group).
"""

from __future__ import annotations

from shared.config import settings
from shared.i18n import t
from shared.logging import get_logger
from shared.models.city import City
from shared.models.news import News

log = get_logger("telegram_admin")


class TelegramAdminService:
    """Administrative Telegram operations triggered outside the bot process."""

    def __init__(self, token: str | None = None, group_id: int | None = None) -> None:
        self.token = token or settings.telegram_bot_token
        self.group_id = group_id or settings.telegram_moderation_group_id

    def _bot(self):  # type: ignore[no-untyped-def]
        from aiogram import Bot

        if not self.token:
            raise RuntimeError("Telegram bot token not configured")
        return Bot(token=self.token)

    async def create_city_topic(self, city: City) -> int | None:
        """Create a forum topic for a city in the moderation group.

        Returns the topic (thread) id, or ``None`` if the group is not a forum
        or the operation failed.
        """
        if not self.group_id:
            log.warning("no_moderation_group_configured")
            return None
        bot = self._bot()
        try:
            topic = await bot.create_forum_topic(chat_id=self.group_id, name=city.name[:128])
            log.info("topic_created", city=city.id, topic=topic.message_thread_id)
            return topic.message_thread_id
        except Exception as exc:  # noqa: BLE001
            log.error("topic_create_failed", city=city.id, error=str(exc))
            return None
        finally:
            await bot.session.close()

    def build_moderation_keyboard(self, news: News, lang: str = "ru"):  # type: ignore[no-untyped-def]
        """Build the inline keyboard shown on a moderation card."""
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        admin_url = f"{settings.admin_panel_url}/news/{news.id}"
        rows = [
            [
                InlineKeyboardButton(
                    text=t("moderation.approve", lang), callback_data=f"mod:approve:{news.id}"
                ),
                InlineKeyboardButton(
                    text=t("moderation.reject", lang), callback_data=f"mod:reject:{news.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("moderation.edit", lang), callback_data=f"mod:edit:{news.id}"
                ),
                InlineKeyboardButton(
                    text=t("moderation.spoiler", lang), callback_data=f"mod:spoiler:{news.id}"
                ),
            ],
            [InlineKeyboardButton(text=t("moderation.open_admin", lang), url=admin_url)],
        ]
        if news.original_url:
            rows.append(
                [InlineKeyboardButton(text=t("moderation.original", lang), url=news.original_url)]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def send_moderation_card(self, news: News, city: City, lang: str = "ru") -> int | None:
        """Send the moderation card to the city's topic. Returns the message id."""
        if not self.group_id:
            return None
        bot = self._bot()
        try:
            title = news.title or news.original_title or "—"
            preview = (news.text or news.original_text or "")[:600]
            score = f"{news.match_score:.0%}" if news.match_score is not None else "—"
            body = (
                f"🆕 <b>{title}</b>\n\n"
                f"{preview}\n\n"
                f"🏙 {city.name} · 🎯 {score} · 🆔 {news.id}"
            )
            kwargs: dict = {
                "chat_id": self.group_id,
                "text": body,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": self.build_moderation_keyboard(news, lang),
            }
            if city.telegram_topic_id:
                kwargs["message_thread_id"] = city.telegram_topic_id
            message = await bot.send_message(**kwargs)
            log.info("moderation_card_sent", news=news.id, message=message.message_id)
            return message.message_id
        except Exception as exc:  # noqa: BLE001
            log.error("moderation_card_failed", news=news.id, error=str(exc))
            return None
        finally:
            await bot.session.close()
