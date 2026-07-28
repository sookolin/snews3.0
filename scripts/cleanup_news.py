"""Wipe the news history: database rows, media files and Telegram messages.

Intended for cleaning up after testing, so the panel starts from a clean slate
with news ids counted from 1 again.

What it does (in this order):

1. deletes every published post from its Telegram channel(s);
2. deletes every moderation card from the moderation group / topics;
3. deletes news rows (versions and media assets cascade) and the media files;
4. resets the ``news.id`` sequence so the next item is #1.

Usage::

    python -m scripts.cleanup_news --dry-run     # show what would be removed
    python -m scripts.cleanup_news               # ask for confirmation, then run
    python -m scripts.cleanup_news --yes         # no confirmation (CI/scripted)
    python -m scripts.cleanup_news --keep-telegram   # DB only, leave Telegram

Only news are touched: cities, sources, channels, templates, users and settings
are left untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil

from sqlalchemy import delete, func, select, text

from shared.config import settings
from shared.database import engine, session_scope
from shared.logging import configure_logging, get_logger
from shared.models.news import News, NewsVersion

log = get_logger("cleanup_news")


async def _delete_telegram_messages(dry_run: bool) -> tuple[int, int]:
    """Remove published posts and moderation cards from Telegram.

    Returns ``(posts_removed, cards_removed)``. Missing/too-old messages are
    skipped silently — Telegram only allows bots to delete recent messages.
    """
    if not settings.telegram_bot_token:
        log.warning("no_bot_token_skipping_telegram")
        return 0, 0

    from aiogram import Bot

    posts = cards = 0
    bot = Bot(token=settings.telegram_bot_token)
    try:
        async with session_scope() as session:
            rows = (
                await session.scalars(
                    select(News).where(
                        (News.published_message_ids != {})
                        | (News.moderation_message_id.is_not(None))
                    )
                )
            ).all()

            for news in rows:
                # 1) Posts in the city channels.
                for chat_id, message_ids in (news.published_message_ids or {}).items():
                    target: int | str = chat_id
                    if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
                        target = int(chat_id)
                    for message_id in message_ids or []:
                        if dry_run:
                            posts += 1
                            continue
                        try:
                            await bot.delete_message(chat_id=target, message_id=message_id)
                            posts += 1
                        except Exception as exc:  # noqa: BLE001 - gone or too old
                            log.debug(
                                "post_delete_skipped",
                                news=news.id, chat=chat_id, message=message_id, error=str(exc),
                            )

                # 2) Moderation card in the group topic.
                if news.moderation_message_id and settings.telegram_moderation_group_id:
                    if dry_run:
                        cards += 1
                    else:
                        try:
                            await bot.delete_message(
                                chat_id=settings.telegram_moderation_group_id,
                                message_id=news.moderation_message_id,
                            )
                            cards += 1
                        except Exception as exc:  # noqa: BLE001
                            log.debug(
                                "card_delete_skipped",
                                news=news.id, message=news.moderation_message_id, error=str(exc),
                            )
    finally:
        await bot.session.close()
    return posts, cards


def _delete_media_files(dry_run: bool) -> int:
    """Remove downloaded news media from disk (``MEDIA_ROOT/news``)."""
    root = os.path.join(settings.media_root, "news")
    if not os.path.isdir(root):
        return 0
    count = sum(len(files) for _, _, files in os.walk(root))
    if not dry_run:
        shutil.rmtree(root, ignore_errors=True)
    return count


async def _purge_database(dry_run: bool, reset_ids: bool) -> int:
    """Delete all news rows and (optionally) reset the id sequence."""
    async with session_scope() as session:
        total = await session.scalar(select(func.count()).select_from(News)) or 0
        if dry_run or not total:
            return total

        # Versions have ON DELETE CASCADE, but clear them explicitly so the
        # script also works on databases created before that constraint.
        await session.execute(delete(NewsVersion))
        await session.execute(delete(News))

        if reset_ids:
            dialect = engine.dialect.name
            try:
                if dialect == "postgresql":
                    await session.execute(text("ALTER SEQUENCE news_id_seq RESTART WITH 1"))
                    await session.execute(
                        text("ALTER SEQUENCE news_versions_id_seq RESTART WITH 1")
                    )
                elif dialect == "sqlite":
                    await session.execute(
                        text("DELETE FROM sqlite_sequence WHERE name IN "
                             "('news', 'news_versions')")
                    )
            except Exception as exc:  # noqa: BLE001 - sequence naming differs
                log.warning("id_reset_failed", error=str(exc))
        return total


async def main() -> None:
    parser = argparse.ArgumentParser(description="Очистка базы новостей и сообщений Telegram")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не удалять")
    parser.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    parser.add_argument(
        "--keep-telegram",
        action="store_true",
        help="не удалять сообщения из канала и топика (только база)",
    )
    parser.add_argument(
        "--keep-ids", action="store_true", help="не сбрасывать нумерацию news.id"
    )
    args = parser.parse_args()

    configure_logging()

    async with session_scope() as session:
        total = await session.scalar(select(func.count()).select_from(News)) or 0
    print(f"Новостей в базе: {total}")

    if args.dry_run:
        posts, cards = (0, 0) if args.keep_telegram else await _delete_telegram_messages(True)
        files = _delete_media_files(True)
        print(
            "Было бы удалено: "
            f"новостей {total}, сообщений в каналах {posts}, карточек модерации {cards}, "
            f"файлов медиа {files}"
        )
        return

    if not args.yes:
        print(
            "Будут безвозвратно удалены все новости, их версии, вложения, "
            "посты в каналах и карточки модерации."
        )
        if input("Введите 'DELETE' для подтверждения: ").strip() != "DELETE":
            print("Отменено.")
            return

    posts = cards = 0
    if not args.keep_telegram:
        posts, cards = await _delete_telegram_messages(False)
    files = _delete_media_files(False)
    removed = await _purge_database(False, reset_ids=not args.keep_ids)

    print(
        "Готово. Удалено: "
        f"новостей {removed}, сообщений в каналах {posts}, карточек модерации {cards}, "
        f"файлов медиа {files}"
    )
    if not args.keep_ids:
        print("Нумерация новостей сброшена — следующая новость получит id 1.")


if __name__ == "__main__":
    asyncio.run(main())
