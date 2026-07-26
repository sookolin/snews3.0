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

    @staticmethod
    def _normalize_chat_id(raw: str) -> int | str:
        """Normalise a chat identifier.

        Accepts numeric ids (``-100123``), ``@username``, ``username``,
        ``t.me/username`` or ``https://t.me/username`` and returns a value the
        Bot API accepts (int id or ``@username``).
        """
        value = (raw or "").strip()
        if not value:
            return value
        # Numeric chat id.
        if value.lstrip("-").isdigit():
            return int(value)
        # Strip URL forms → username.
        low = value.lower()
        for prefix in ("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"):
            if low.startswith(prefix):
                value = value[len(prefix):]
                break
        value = value.strip("/")
        # Private invite links / joinchat cannot be used as chat_id.
        if value.startswith("+") or value.startswith("joinchat"):
            return value
        if not value.startswith("@"):
            value = f"@{value}"
        return value

    # Map our color names → Telegram Bot API 9.4 button styles.
    _COLOR_TO_STYLE = {
        "blue": "primary",
        "primary": "primary",
        "green": "success",
        "success": "success",
        "red": "danger",
        "danger": "danger",
    }

    def _build_keyboard(self, buttons: list):  # type: ignore[no-untyped-def]
        """Build an InlineKeyboardMarkup from rows of {text,url,color} dicts.

        Colors are mapped to Bot API 9.4 button ``style`` values
        (primary/success/danger) so they render coloured in Telegram.
        """
        if not buttons:
            return None
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        supports_style = "style" in InlineKeyboardButton.model_fields
        rows = []
        for row in buttons:
            cells = []
            for btn in row:
                text = (btn or {}).get("text")
                url = (btn or {}).get("url")
                if not (text and url):
                    continue
                kwargs: dict = {"text": text, "url": url}
                style = self._COLOR_TO_STYLE.get((btn or {}).get("color") or "")
                if style and supports_style:
                    kwargs["style"] = style
                cells.append(InlineKeyboardButton(**kwargs))
            if cells:
                rows.append(cells)
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    def _input_file(self, media: MediaAsset):  # type: ignore[no-untyped-def]
        from aiogram.types import FSInputFile, URLInputFile

        # Prefer the locally processed (watermarked) file so the watermark is
        # actually delivered. Fall back to raw local file, then telegram file_id,
        # then remote URL.
        path = media.processed_path or media.file_path
        if path:
            abs_path = path if os.path.isabs(path) else os.path.join(settings.media_root, path)
            if os.path.exists(abs_path):
                return FSInputFile(abs_path)
        if media.telegram_file_id:
            return media.telegram_file_id
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
        chat_id: int | str = self._normalize_chat_id(self.channel.chat_id)

        common: dict = {"chat_id": chat_id}
        if self.channel.topic_id:
            common["message_thread_id"] = self.channel.topic_id

        from shared.services.html_sanitizer import sanitize_telegram_html

        request.text = sanitize_telegram_html(request.text)
        enabled_media = [m for m in request.media if m.is_enabled]
        message_ids: list[int] = []
        keyboard = self._build_keyboard(request.buttons)
        text = request.text[:_TELEGRAM_TEXT_LIMIT]

        try:
            if not enabled_media:
                # ── Plain text ──────────────────────────────────────────────
                msg = await bot.send_message(
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=request.disable_web_preview,
                    reply_markup=keyboard,
                    **common,
                )
                message_ids.append(msg.message_id)
            else:
                # ── Split media into Telegram-compatible groups ─────────────
                # Photos+videos may share one album; documents, audio, and
                # single-only types (voice, video_note, animation) go separately.
                groups = self._split_media_groups(enabled_media)
                caption_used = False
                for group in groups:
                    caption = None if caption_used else text
                    ids = await self._send_group(
                        bot, group, caption, common,
                        keyboard if not caption_used else None,
                    )
                    message_ids.extend(ids)
                    caption_used = True

            # ── Optional geolocation as a follow-up message ──────────────────
            if request.latitude is not None and request.longitude is not None:
                if request.location_title:
                    loc = await bot.send_venue(
                        latitude=request.latitude,
                        longitude=request.longitude,
                        title=request.location_title,
                        address=request.location_address or request.location_title,
                        **common,
                    )
                else:
                    loc = await bot.send_location(
                        latitude=request.latitude,
                        longitude=request.longitude,
                        **common,
                    )
                message_ids.append(loc.message_id)

            return PublishResult(success=True, message_ids=message_ids)
        except Exception as exc:  # noqa: BLE001
            log.error("telegram_publish_failed", channel=self.channel.id, error=str(exc))
            return PublishResult(success=False, error=str(exc))
        finally:
            await bot.session.close()

    @staticmethod
    def _split_media_groups(media: list[MediaAsset]) -> list[list[MediaAsset]]:
        """Split media into groups Telegram allows in a single send_media_group.

        Rules: photos & videos can mix; documents only with documents; audio
        only with audio; voice/video_note/animation must be sent individually.
        """
        visual: list[MediaAsset] = []
        documents: list[MediaAsset] = []
        audio: list[MediaAsset] = []
        singles: list[MediaAsset] = []
        for m in media:
            if m.type in (MediaType.PHOTO, MediaType.VIDEO):
                visual.append(m)
            elif m.type == MediaType.DOCUMENT:
                documents.append(m)
            elif m.type == MediaType.AUDIO:
                audio.append(m)
            else:  # ANIMATION, VOICE, VIDEO_NOTE
                singles.append(m)

        groups: list[list[MediaAsset]] = []
        # chunk visual/docs/audio into batches of 10 (Telegram album limit)
        for bucket in (visual, documents, audio):
            for i in range(0, len(bucket), 10):
                groups.append(bucket[i : i + 10])
        groups.extend([m] for m in singles)
        return [g for g in groups if g]

    async def _send_group(  # type: ignore[no-untyped-def]
        self, bot, group: list[MediaAsset], caption: str | None, common: dict, keyboard,
    ) -> list[int]:
        """Send one compatible media group (or a single item)."""
        from aiogram.enums import ParseMode
        from aiogram.types import (
            InputMediaAudio,
            InputMediaDocument,
            InputMediaPhoto,
            InputMediaVideo,
        )

        cap = (caption or "")[:_TELEGRAM_CAPTION_LIMIT] if caption else None

        # Single item → direct send (supports inline keyboard).
        if len(group) == 1:
            media = group[0]
            file = self._input_file(media)
            spoiler = bool(media.is_spoiler)
            kwargs = {"caption": cap, "parse_mode": ParseMode.HTML, "reply_markup": keyboard, **common}
            if media.type == MediaType.PHOTO:
                msg = await bot.send_photo(photo=file, has_spoiler=spoiler, **kwargs)
            elif media.type == MediaType.VIDEO:
                msg = await bot.send_video(video=file, has_spoiler=spoiler, **kwargs)
            elif media.type == MediaType.ANIMATION:
                msg = await bot.send_animation(animation=file, has_spoiler=spoiler, **kwargs)
            elif media.type == MediaType.AUDIO:
                msg = await bot.send_audio(audio=file, **kwargs)
            elif media.type == MediaType.VOICE:
                msg = await bot.send_voice(voice=file, caption=cap, parse_mode=ParseMode.HTML,
                                           reply_markup=keyboard, **common)
            elif media.type == MediaType.VIDEO_NOTE:
                msg = await bot.send_video_note(video_note=file, reply_markup=keyboard, **common)
            else:
                msg = await bot.send_document(document=file, **kwargs)
            return [msg.message_id]

        # Multi-item album.
        items: list = []
        for idx, media in enumerate(group):
            file = self._input_file(media)
            c = cap if idx == 0 else None
            spoiler = bool(media.is_spoiler)
            if media.type == MediaType.PHOTO:
                items.append(InputMediaPhoto(media=file, caption=c, parse_mode=ParseMode.HTML,
                                             has_spoiler=spoiler))
            elif media.type == MediaType.VIDEO:
                items.append(InputMediaVideo(media=file, caption=c, parse_mode=ParseMode.HTML,
                                             has_spoiler=spoiler))
            elif media.type == MediaType.AUDIO:
                items.append(InputMediaAudio(media=file, caption=c, parse_mode=ParseMode.HTML))
            else:
                items.append(InputMediaDocument(media=file, caption=c, parse_mode=ParseMode.HTML))
        messages = await bot.send_media_group(media=items, **common)
        ids = [m.message_id for m in messages]
        # Albums can't carry a keyboard; send it as a follow-up if present.
        if keyboard is not None:
            kb_msg = await bot.send_message(text="\u2063", reply_markup=keyboard, **common)
            ids.append(kb_msg.message_id)
        return ids
