"""News moderation helpers shared by the API and the Telegram bot.

Centralises the side effects of a moderation decision:

* render the post exactly as it will be published (for the card and preview);
* update the moderation card in the topic (status, moderator, buttons);
* delete or edit already published Telegram messages when the news changes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.logging import get_logger
from shared.models.city import City
from shared.models.news import News
from shared.models.source import Source
from shared.models.template import Template
from shared.models.user import User
from shared.services.template_renderer import TemplateRenderer

log = get_logger("news_moderation")


class NewsModerationService:
    """Render news and synchronise Telegram state after moderation actions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── rendering ───────────────────────────────────────────────────────────
    async def resolve_source_name(self, news: News) -> str:
        """Effective source label (manual override wins, hidden → empty)."""
        if news.hide_source:
            return ""
        if news.source_name:
            return news.source_name
        if news.source_id:
            source = await self.session.get(Source, news.source_id)
            if source:
                return source.name
        return ""

    @staticmethod
    def resolve_source_url(news: News) -> str:
        """Effective link to the original publication."""
        if news.hide_source:
            return ""
        return news.source_url_override or news.original_url or ""

    async def render(self, news: News) -> str:
        """Render the news through its effective template."""
        template: Template | None = None
        if news.template_id:
            template = await self.session.get(Template, news.template_id)
        if template is None and news.city_id:
            city = await self.session.get(City, news.city_id)
            if city and city.template_id:
                template = await self.session.get(Template, city.template_id)
        if template is None:
            template = await self.session.scalar(
                select(Template).where(Template.is_default.is_(True)).limit(1)
            )
        if template is None:
            template = await self.session.scalar(select(Template).limit(1))
        if template is None:
            return news.text or news.original_text or ""

        city_name = ""
        if news.city_id:
            city = await self.session.get(City, news.city_id)
            city_name = city.name if city else ""

        author = "" if news.submitted_anonymously else (news.author_name or "")

        # Load global tags so premium tg-emoji placeholders render in the card.
        global_tags: list[dict] = []
        try:
            from shared.services.settings_service import SettingsService
            import json as _json
            raw = await SettingsService(self.session).get("templates.global_tags", "") or ""
            if isinstance(raw, str) and raw.strip().startswith("["):
                global_tags = _json.loads(raw)
            elif isinstance(raw, list):
                global_tags = raw
        except Exception:
            pass

        return TemplateRenderer().render(
            template,
            title=news.title or news.original_title or "",
            text=news.text or news.original_text or "",
            source=await self.resolve_source_name(news),
            source_url=self.resolve_source_url(news),
            city=city_name,
            author=author,
            emoji=news.emoji or "",
            global_tags=global_tags,
        )

    # ── moderation card ─────────────────────────────────────────────────────
    async def moderator_label(self, user_id: int | None) -> str | None:
        if not user_id:
            return None
        user = await self.session.get(User, user_id)
        if user is None:
            return None
        return user.full_name or user.email

    async def update_card(
        self,
        news: News,
        *,
        status_line: str,
        keep_buttons: bool = False,
    ) -> bool:
        """Refresh the moderation card for this news item."""
        if not news.city_id or not news.moderation_message_id:
            return False
        city = await self.session.get(City, news.city_id)
        if city is None:
            return False
        # Media must be loaded so a photo card is updated as a caption.
        await self.session.refresh(news, attribute_names=["media"])

        from shared.services.settings_service import SettingsService
        from shared.services.telegram_admin import TelegramAdminService

        cfg = SettingsService(self.session)
        tz_offset = int(await cfg.get("ui.timezone_offset_hours", 3))
        card_template = (await cfg.get("moderation.card_template", "")) or None
        return await TelegramAdminService().update_moderation_card(
            news,
            city,
            status_line=status_line,
            keep_buttons=keep_buttons,
            lang=city.language,
            rendered=await self.render(news),
            source_name=await self.resolve_source_name(news),
            moderator=await self.moderator_label(news.moderated_by),
            tz_offset=tz_offset,
            template=card_template,
        )

    # ── published message sync ──────────────────────────────────────────────
    async def delete_published(self, news: News) -> int:
        """Delete every already published Telegram message for this news.

        Returns the number of messages actually removed. Clears
        ``published_message_ids`` so the post can be published again later.
        """
        if not news.published_message_ids or not settings.telegram_bot_token:
            return 0

        from aiogram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        removed = 0
        try:
            for chat_id, message_ids in (news.published_message_ids or {}).items():
                target: int | str = chat_id
                if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
                    target = int(chat_id)
                for message_id in message_ids or []:
                    try:
                        await bot.delete_message(chat_id=target, message_id=message_id)
                        removed += 1
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "published_delete_failed",
                            news=news.id, chat=chat_id, message=message_id, error=str(exc),
                        )
        finally:
            await bot.session.close()

        news.published_message_ids = {}
        news.published_at = None
        return removed

    async def edit_published(self, news: News) -> int:
        """Update the text of already published messages after an edit.

        Only text-only posts can be edited in place; for posts with media the
        caption of the first message is updated instead. Returns the number of
        messages successfully updated.
        """
        if not news.published_message_ids or not settings.telegram_bot_token:
            return 0

        from aiogram import Bot
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        from shared.services.html_sanitizer import sanitize_telegram_html

        text = sanitize_telegram_html(await self.render(news))

        # Rebuild the inline keyboard so it is preserved after the edit.
        # Telegram removes reply_markup when it is not explicitly passed.
        reply_markup: InlineKeyboardMarkup | None = None
        raw_buttons: list = news.buttons or []
        if raw_buttons:
            keyboard = [
                [
                    InlineKeyboardButton(text=btn.get("text", ""), url=btn.get("url") or None)
                    for btn in row
                    if btn.get("text")
                ]
                for row in raw_buttons
            ]
            keyboard = [row for row in keyboard if row]
            if keyboard:
                reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        bot = Bot(token=settings.telegram_bot_token)
        updated = 0
        try:
            for chat_id, message_ids in (news.published_message_ids or {}).items():
                target: int | str = chat_id
                if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
                    target = int(chat_id)
                if not message_ids:
                    continue
                first = message_ids[0]
                try:
                    await bot.edit_message_text(
                        chat_id=target, message_id=first, text=text[:4096],
                        parse_mode="HTML", disable_web_page_preview=True,
                        reply_markup=reply_markup,
                    )
                    updated += 1
                except Exception:  # noqa: BLE001
                    # Media posts: text cannot be edited, try the caption.
                    try:
                        await bot.edit_message_caption(
                            chat_id=target, message_id=first, caption=text[:1024],
                            parse_mode="HTML", reply_markup=reply_markup,
                        )
                        updated += 1
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "published_edit_failed",
                            news=news.id, chat=chat_id, message=first, error=str(exc),
                        )
        finally:
            await bot.session.close()
        return updated
