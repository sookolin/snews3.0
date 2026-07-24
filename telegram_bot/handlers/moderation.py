"""Moderation handlers — inline button callbacks from moderation cards.

Callback data format: ``mod:<action>:<news_id>``.
Only users linked (by ``telegram_id``) to an account with the
``news:moderate`` permission may approve/reject.
"""

from __future__ import annotations

import contextlib

from aiogram import F, Router
from aiogram.types import CallbackQuery

from shared.database import session_scope
from shared.enums import NewsStatus, Permission
from shared.i18n import t
from shared.logging import get_logger
from shared.models.news import News
from shared.security import has_permission
from shared.services.user_service import UserService

router = Router(name="moderation")
log = get_logger("bot.moderation")


async def _authorized(telegram_id: int) -> tuple[bool, str]:
    """Return (allowed, language) for a moderating Telegram user."""
    async with session_scope() as session:
        user = await UserService(session).get_by_telegram_id(telegram_id)
        if user is None or not user.is_active:
            return False, "ru"
        return has_permission(user.role, Permission.NEWS_MODERATE), user.language


@router.callback_query(F.data.startswith("mod:"))
async def handle_moderation(callback: CallbackQuery) -> None:
    """Dispatch a moderation action from an inline button."""
    if not callback.data or callback.from_user is None:
        await callback.answer()
        return

    try:
        _, action, raw_id = callback.data.split(":", 2)
        news_id = int(raw_id)
    except (ValueError, IndexError):
        await callback.answer("Invalid action")
        return

    allowed, lang = await _authorized(callback.from_user.id)
    if not allowed:
        await callback.answer(t("moderation.no_permission", lang), show_alert=True)
        return

    if action == "approve":
        await _approve(callback, news_id, lang)
    elif action == "reject":
        await _reject(callback, news_id, lang)
    elif action == "spoiler":
        await _toggle_spoiler(callback, news_id, lang)
    elif action == "edit":
        await callback.answer("Открыть карточку в админке для редактирования.", show_alert=False)
    else:
        await callback.answer()


async def _approve(callback: CallbackQuery, news_id: int, lang: str) -> None:
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Not found", show_alert=True)
            return
        user = await UserService(session).get_by_telegram_id(callback.from_user.id)
        news.status = NewsStatus.APPROVED
        news.moderated_by = user.id if user else None
        await session.commit()

    # Enqueue publication via the worker queue (decoupled from the bot process).
    try:
        from workers.tasks import publish_news

        publish_news.delay(news_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("publish_enqueue_failed", news=news_id, error=str(exc))

    await callback.answer(t("moderation.approved", lang))
    await _mark_card(callback, "✅ " + t("moderation.approved", lang))


async def _reject(callback: CallbackQuery, news_id: int, lang: str) -> None:
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Not found", show_alert=True)
            return
        user = await UserService(session).get_by_telegram_id(callback.from_user.id)
        news.status = NewsStatus.REJECTED
        news.moderated_by = user.id if user else None
        await session.commit()
    await callback.answer(t("moderation.rejected", lang))
    await _mark_card(callback, "❌ " + t("moderation.rejected", lang))


async def _toggle_spoiler(callback: CallbackQuery, news_id: int, lang: str) -> None:
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Not found", show_alert=True)
            return
        news.is_spoiler = not news.is_spoiler
        state = "ON" if news.is_spoiler else "OFF"
        await session.commit()
    await callback.answer(f"{t('moderation.spoiler', lang)}: {state}")


async def _mark_card(callback: CallbackQuery, suffix: str) -> None:
    """Append a status line to the moderation card and drop the keyboard."""
    if callback.message is None:
        return
    try:
        text = (callback.message.html_text or callback.message.text or "") + f"\n\n{suffix}"
        await callback.message.edit_text(text, reply_markup=None)
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)
