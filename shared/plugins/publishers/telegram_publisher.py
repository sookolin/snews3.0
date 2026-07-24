"""Telegram publisher using aiogram Bot.

Handles text-only posts, single media and albums, spoilers, topic threads and
custom captions. Media are uploaded from local processed paths, remote URLs or
reused ``telegram_file_id`` values.
"""

from __future__ import annotations

import os

from shared.config import settings
from shared.enums import MediaType
from shared.exceptions import PublishError
from shared.logging import get_logger
from shared.models.media import MediaAsset
from shared.plugins.publishers.base import (
    BasePublisher,
    PublishRequest,
    PublishResult,
    publisher_registry,
)

log = get_logger("publisher.telegram")

_TELEGRAM_CAPTION_LIMIT = 1024
_TELEGRAM_TEXT_LIMIT = 4096


@publisher_registry.register("telegram")
class TelegramPublisher(BasePublisher):
    """Publish a news item to a Telegram channel/chat/topic."""

    publisher_type = "telegram"

    def _input_file(self, media: MediaAsset):  # type: ignore[no-untyped-def]
        from aiogram.types import FSInputFile, URLInputFile

        path = media.processed_path or media.file_path
        if media.telegram_file_id:
            return media.telegram_file_id
        if path:
            abs_path = path if os.path.isabs(path) else os.path.join(settings.media_root, path)
            if os.path.exists(abs_path):
                return FSInputFile(abs_path)
        if media.remote_url:
            return URLInputFile(media.remote_url)
        raise PublishError(f"Media {media.id} has no usable source")

    async def publish(self, request: PublishRequest) -> PublishResult:  # noqa: C901
        from aiogram import Bot
        from aiogram.enums import ParseMode
        from aiogram.types import (
            InputMediaAudio,
            InputMediaDocument,
            InputMediaPhoto,
            InputMediaVideo,
        )

        if not settings.telegram_bot_token:
            return PublishResult(success=False, error="Bot token not configured")

        bot = Bot(token=settings.telegram_bot_token)
        chat_id: int | str = self.channel.chat_id
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)

        common: dict = {"chat_id": chat_id}
        if self.channel.topic_id:
            common["message_thread_id"] = self.channel.topic_id

        enabled_media = [m for m in request.media if m.is_enabled]

        try:
            # ── No media: plain text ────────────────────────────────────────
            if not enabled_media:
                msg = await bot.send_message(
                    text=request.text[:_TELEGRAM_TEXT_LIMIT],
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=request.disable_web_preview,
                    **common,
                )
                return PublishResult(success=True, message_ids=[msg.message_id])

            # ── Single media ────────────────────────────────────────────────
            if len(enabled_media) == 1:
                media = enabled_media[0]
                caption = (media.caption or request.text)[:_TELEGRAM_CAPTION_LIMIT]
                spoiler = request.is_spoiler or media.is_spoiler
                file = self._input_file(media)
                kwargs = {"caption": caption, "parse_mode": ParseMode.HTML, **common}
                if media.type == MediaType.PHOTO:
                    msg = await bot.send_photo(photo=file, has_spoiler=spoiler, **kwargs)
                elif media.type in (MediaType.VIDEO, MediaType.ANIMATION):
                    msg = await bot.send_video(video=file, has_spoiler=spoiler, **kwargs)
                elif media.type == MediaType.AUDIO:
                    msg = await bot.send_audio(audio=file, **kwargs)
                elif media.type == MediaType.VOICE:
                    msg = await bot.send_voice(voice=file, **common)
                elif media.type == MediaType.VIDEO_NOTE:
                    msg = await bot.send_video_note(video_note=file, **common)
                else:
                    msg = await bot.send_document(document=file, **kwargs)
                return PublishResult(success=True, message_ids=[msg.message_id])

            # ── Album (media group) ─────────────────────────────────────────
            group: list = []
            for idx, media in enumerate(enabled_media):
                file = self._input_file(media)
                caption = request.text[:_TELEGRAM_CAPTION_LIMIT] if idx == 0 else None
                spoiler = request.is_spoiler or media.is_spoiler
                if media.type == MediaType.PHOTO:
                    group.append(
                        InputMediaPhoto(
                            media=file,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            has_spoiler=spoiler,
                        )
                    )
                elif media.type in (MediaType.VIDEO, MediaType.ANIMATION):
                    group.append(
                        InputMediaVideo(
                            media=file,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            has_spoiler=spoiler,
                        )
                    )
                elif media.type == MediaType.AUDIO:
                    group.append(
                        InputMediaAudio(media=file, caption=caption, parse_mode=ParseMode.HTML)
                    )
                else:
                    group.append(
                        InputMediaDocument(media=file, caption=caption, parse_mode=ParseMode.HTML)
                    )
            messages = await bot.send_media_group(media=group, **common)
            return PublishResult(success=True, message_ids=[m.message_id for m in messages])
        except Exception as exc:  # noqa: BLE001
            log.error("telegram_publish_failed", channel=self.channel.id, error=str(exc))
            return PublishResult(success=False, error=str(exc))
        finally:
            await bot.session.close()
