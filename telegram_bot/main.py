"""Bot entrypoint: dispatcher setup, router registration, long-polling/webhook."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from shared.config import settings
from shared.logging import configure_logging, get_logger
from telegram_bot.handlers import moderation, submission

log = get_logger("bot")


def build_dispatcher() -> Dispatcher:
    """Create a dispatcher with Redis FSM storage and registered routers."""
    storage = RedisStorage.from_url(f"{settings.redis_url}")
    dp = Dispatcher(storage=storage)
    dp.include_router(submission.router)
    dp.include_router(moderation.router)
    return dp


async def main() -> None:
    """Run the bot with long polling."""
    configure_logging()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    log.info("bot_starting")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
