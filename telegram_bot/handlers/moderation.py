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
from shared.security import user_has_permission
from shared.services.user_service import UserService

router = Router(name="moderation")
log = get_logger("bot.moderation")


async def _authorized(telegram_id: int) -> tuple[bool, str]:
    """Return (allowed, language) for a moderating Telegram user."""
    async with session_scope() as session:
        user = await UserService(session).get_by_telegram_id(telegram_id)
        if user is None or not user.is_active:
            return False, "ru"
        return user_has_permission(user, Permission.NEWS_MODERATE), user.language


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
    elif action == "now":
        await _approve(callback, news_id, lang, immediately=True)
    elif action == "reject":
        await _reject(callback, news_id, lang)
    elif action == "spoiler":
        await _toggle_spoiler(callback, news_id, lang)
    elif action == "delete":
        await _delete(callback, news_id, lang)
    elif action == "purge":
        await _delete(callback, news_id, lang, purge=True)
    elif action == "unpublish":
        await _unpublish(callback, news_id, lang)
    elif action == "edit":
        await callback.answer("Откройте карточку в админке для редактирования.", show_alert=False)
    else:
        await callback.answer()


async def _approve(
    callback: CallbackQuery,
    news_id: int,
    lang: str,
    *,
    immediately: bool = False,
    all_cities: bool = False,
) -> None:
    """Approve and queue publication.

    ``immediately`` skips the publication queue; ``all_cities`` publishes the
    same item to the channels of every active city.
    """
    from datetime import datetime, timezone

    who = "—"
    slot = "immediate"
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Новость не найдена", show_alert=True)
            return
        if news.published_message_ids:
            await callback.answer("Новость уже опубликована", show_alert=True)
            return

        user = await UserService(session).get_by_telegram_id(callback.from_user.id)
        news.status = NewsStatus.APPROVED
        news.moderated_by = user.id if user else None
        news.processed_at = datetime.now(timezone.utc)
        if immediately:
            news.publish_immediately = True
        if user:
            who = user.full_name or user.email

        try:
            from workers.tasks import _schedule_publication

            slot = await _schedule_publication(session, news)
        except Exception as exc:  # noqa: BLE001
            log.warning("publish_enqueue_failed", news=news_id, error=str(exc))
        await session.commit()

    # ``all_cities`` used to fan out to EVERY active city. Now a news item
    # already carries its own target cities and the normal publish path sends
    # it to all of their channels in one go, so the "Во все каналы" button just
    # publishes the item to its intended channels — no separate task needed.
    await callback.answer(t("moderation.approved", lang))
    suffix = "" if slot == "immediate" else f" · в очереди на {slot}"
    scope = " · во все каналы города" if all_cities else ""
    await _mark_card(
        callback,
        f"✅ {t('moderation.approved', lang)} · {who}{suffix}{scope}",
        keep_buttons=True,
    )


async def _unpublish(callback: CallbackQuery, news_id: int, lang: str) -> None:
    """Withdraw a published post from the channels, keeping it in the panel."""
    who = "—"
    removed = 0
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Новость не найдена", show_alert=True)
            return
        from shared.services.news_moderation import NewsModerationService

        user = await UserService(session).get_by_telegram_id(callback.from_user.id)
        if user:
            who = user.full_name or user.email
        removed = await NewsModerationService(session).delete_published(news)
        # WITHDRAWN records that the post was live and is now taken down; the
        # card keeps its buttons so it can be published again.
        news.status = NewsStatus.WITHDRAWN
        if user:
            news.moderated_by = user.id
        await session.commit()

    await callback.answer(f"Публикация снята ({removed})")
    await _mark_card(
        callback, f"↩️ Публикация снята · {who} — можно опубликовать заново", keep_buttons=True
    )


async def _reject(callback: CallbackQuery, news_id: int, lang: str) -> None:
    who = "—"
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is None:
            await callback.answer("Not found", show_alert=True)
            return
        user = await UserService(session).get_by_telegram_id(callback.from_user.id)
        news.status = NewsStatus.REJECTED
        news.moderated_by = user.id if user else None
        if user:
            who = user.full_name or user.email
        await session.commit()
    await callback.answer(t("moderation.rejected", lang))
    await _mark_card(
        callback, f"❌ {t('moderation.rejected', lang)} · {who}", keep_buttons=True
    )


async def _delete(
    callback: CallbackQuery, news_id: int, lang: str, *, purge: bool = False
) -> None:
    """Delete the news everywhere: channels, admin panel and (visually) the card."""
    who = "—"
    async with session_scope() as session:
        news = await session.get(News, news_id)
        if news is not None:
            from shared.services.news_moderation import NewsModerationService

            user = await UserService(session).get_by_telegram_id(callback.from_user.id)
            if user:
                who = user.full_name or user.email
            # Remove already published messages from the channels first.
            await NewsModerationService(session).delete_published(news)
            await session.delete(news)
            await session.commit()

    await callback.answer(t("moderation.deleted", lang))
    label = "🗑 Удалено полностью" if purge else f"🗑 {t('moderation.deleted', lang)}"
    await _mark_card(callback, f"{label} · {who}")


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


async def _mark_card(
    callback: CallbackQuery, suffix: str, *, keep_buttons: bool = False
) -> None:
    """Refresh the card after a decision, showing the current status.

    The card is rebuilt from the fresh news state (same renderer the site uses),
    so its status tags — including "изменено" and "отозвано" — always match the
    admin panel. Falls back to appending the status line if the rebuild fails.
    """
    message = callback.message
    if message is None:
        return

    news_id: int | None = None
    with contextlib.suppress(Exception):
        news_id = int((callback.data or "").split(":")[-1])

    # Preferred path: rebuild the whole card through the shared service.
    if news_id is not None:
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                news = await session.get(News, news_id)
                if news is not None:
                    from shared.services.news_moderation import NewsModerationService

                    if await NewsModerationService(session).update_card(
                        news, status_line=suffix, keep_buttons=keep_buttons
                    ):
                        return

    keyboard = None
    if keep_buttons and news_id is not None:
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                news = await session.get(News, news_id)
                if news is not None:
                    from shared.services.telegram_admin import TelegramAdminService

                    keyboard = TelegramAdminService().build_moderation_keyboard(news)

    existing = message.html_text if message.text else (message.caption or "")
    new_text = f"{existing}\n\n{suffix}"
    try:
        if message.text:
            await message.edit_text(new_text, reply_markup=keyboard)
        else:
            await message.edit_caption(caption=new_text[:1024], reply_markup=keyboard)
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await message.edit_reply_markup(reply_markup=keyboard)
