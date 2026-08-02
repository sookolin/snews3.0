"""Telegram admin service — topic creation & moderation card delivery.

Uses a short-lived aiogram Bot instance for administrative actions initiated by
the backend/workers (creating a city's forum topic, sending the moderation card
with inline buttons to the city's topic in the moderation group).
"""

from __future__ import annotations

from shared.config import settings
from shared.enums import NewsStatus
from shared.logging import get_logger
from shared.models.city import City
from shared.models.news import News

log = get_logger("telegram_admin")

#: Human-readable status tags shown on moderation cards.
STATUS_TAGS: dict[str, str] = {
    "processing": "⏳ обработка",
    "pending": "🟡 на модерации",
    "approved": "🟢 одобрено",
    "scheduled": "🕒 запланировано",
    "published": "📤 опубликовано",
    "withdrawn": "↩️ отозвано",
    "rejected": "🔴 отклонено",
    "failed": "⚠️ ошибка",
}


def _is_public_url(url: str) -> bool:
    """Whether Telegram will accept the URL in an inline keyboard button.

    Telegram rejects localhost / bare-IP / non-http(s) targets with
    "Wrong HTTP URL", which fails the entire sendMessage call.
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return False
    # Private ranges and hosts without a dot (e.g. docker service names).
    if host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.")):
        return False
    return "." in host


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

    async def fetch_chat_info(self, chat_id: str) -> dict | None:
        """Read a channel's real title, username and avatar URL from Telegram.

        The bot must be a member/admin of the chat. The avatar is downloaded to
        MEDIA_ROOT so the admin panel can display it without a Telegram token.
        """
        import os

        from shared.plugins.publishers.telegram_publisher import TelegramPublisher

        if not self.token:
            return None
        bot = self._bot()
        try:
            target = TelegramPublisher._normalize_chat_id(chat_id)
            chat = await bot.get_chat(target)
            info: dict = {
                "title": chat.title or chat.full_name or "",
                "username": chat.username or "",
                "avatar_url": None,
            }

            photo = getattr(chat, "photo", None)
            if photo is not None:
                file_id = photo.big_file_id or photo.small_file_id
                if file_id:
                    tg_file = await bot.get_file(file_id)
                    rel_dir = "channels"
                    os.makedirs(os.path.join(settings.media_root, rel_dir), exist_ok=True)
                    safe = str(target).lstrip("@-")
                    rel_path = os.path.join(rel_dir, f"{safe}.jpg")
                    await bot.download_file(
                        tg_file.file_path,
                        destination=os.path.join(settings.media_root, rel_path),
                    )
                    info["avatar_url"] = f"/media/{rel_path.replace(os.sep, '/')}"
            return info
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch_chat_info_failed", chat=chat_id, error=str(exc))
            return None
        finally:
            await bot.session.close()

    async def create_topic(self, name: str) -> int | None:
        """Create an arbitrary forum topic (used for the world-news topic)."""
        if not self.group_id:
            return None
        bot = self._bot()
        try:
            topic = await bot.create_forum_topic(chat_id=self.group_id, name=name[:128])
            return topic.message_thread_id
        except Exception as exc:  # noqa: BLE001
            log.error("create_topic_failed", name=name, error=str(exc))
            return None
        finally:
            await bot.session.close()

    async def delete_messages(self, chat_id: str, message_ids: list[int]) -> int:
        """Delete a batch of messages; returns how many were removed."""
        from shared.plugins.publishers.telegram_publisher import TelegramPublisher

        if not self.token or not message_ids:
            return 0
        bot = self._bot()
        removed = 0
        try:
            target = TelegramPublisher._normalize_chat_id(chat_id)
            for message_id in message_ids:
                try:
                    await bot.delete_message(chat_id=target, message_id=message_id)
                    removed += 1
                except Exception:  # noqa: BLE001 - already gone or too old
                    continue
            return removed
        finally:
            await bot.session.close()

    async def test_topic(self, city: City) -> tuple[bool, str]:
        """Send a test message to the city's topic to verify the binding."""
        if not self.group_id:
            return False, "Не задан ID группы модерации (TELEGRAM_MODERATION_GROUP_ID)"
        bot = self._bot()
        try:
            kwargs: dict = {
                "chat_id": self.group_id,
                "text": f"✅ Проверка привязки топика для города «{city.name}».",
            }
            if city.telegram_topic_id:
                kwargs["message_thread_id"] = city.telegram_topic_id
            msg = await bot.send_message(**kwargs)
            return (
                True,
                f"Сообщение доставлено (id={msg.message_id}, "
                f"topic={city.telegram_topic_id})",
            )
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        finally:
            await bot.session.close()

    def build_moderation_keyboard(self, news: News, lang: str = "ru"):  # type: ignore[no-untyped-def]
        """Build the inline keyboard shown on a moderation card.

        Buttons are coloured via the Bot API 9.4 ``style`` field:
        approve = success (green), reject/delete = danger (red),
        edit = primary (blue link to the admin panel).
        """
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        supports_style = "style" in InlineKeyboardButton.model_fields

        def button(text: str, *, style: str | None = None, **kwargs: object):  # type: ignore[no-untyped-def]
            data = {"text": text, **kwargs}
            if style and supports_style:
                data["style"] = style
            return InlineKeyboardButton(**data)

        admin_url = f"{settings.admin_panel_url.rstrip('/')}/news/{news.id}"
        is_published = bool(news.published_message_ids)

        # Icon-only buttons keep the card compact.
        edit_kwargs: dict = (
            {"url": admin_url}
            if _is_public_url(admin_url)
            else {"callback_data": f"mod:edit:{news.id}"}
        )

        # Buttons carry full text labels (icons alone were unclear).
        if not is_published and news.status in (NewsStatus.APPROVED, NewsStatus.SCHEDULED):
            # Decided but not yet in the channel: allow pushing it out now,
            # taking the decision back, or removing the item entirely.
            rows = [
                [
                    button(
                        "⚡️ Опубликовать сразу",
                        style="success",
                        callback_data=f"mod:now:{news.id}",
                    ),
                    button("❌ Отклонить", style="danger", callback_data=f"mod:reject:{news.id}"),
                ],
                [
                    button("✏️ Редактировать", style="primary", **edit_kwargs),
                    button("🗑 Удалить", style="danger", callback_data=f"mod:delete:{news.id}"),
                ],
            ]
        elif not is_published and news.status == NewsStatus.REJECTED:
            # Rejected items keep a way back: approve again or delete for good.
            rows = [
                [
                    button("✅ Одобрить", style="success", callback_data=f"mod:approve:{news.id}"),
                    button("✏️ Редактировать", style="primary", **edit_kwargs),
                ],
                [
                    button(
                        "🗑 Удалить полностью",
                        style="danger",
                        callback_data=f"mod:purge:{news.id}",
                    )
                ],
            ]
        elif is_published or news.status == NewsStatus.WITHDRAWN:
            # Already handled: allow withdrawing / re-publishing / full removal.
            rows = [
                [button("✏️ Редактировать", style="primary", **edit_kwargs)],
            ]
            if is_published:
                rows.append(
                    [
                        button(
                            "↩️ Снять с публикации",
                            style="primary",
                            callback_data=f"mod:unpublish:{news.id}",
                        )
                    ]
                )
            else:
                rows.append(
                    [
                        button(
                            "📤 Опубликовать снова",
                            style="success",
                            callback_data=f"mod:approve:{news.id}",
                        ),
                    ]
                )
            rows.append(
                [
                    button(
                        "🗑 Удалить полностью",
                        style="danger",
                        callback_data=f"mod:purge:{news.id}",
                    )
                ]
            )
        else:
            rows = [
                [
                    button("✅ Одобрить", style="success", callback_data=f"mod:approve:{news.id}"),
                    button("❌ Отклонить", style="danger", callback_data=f"mod:reject:{news.id}"),
                ],
                [
                    button("✏️ Редактировать", style="primary", **edit_kwargs),
                    button(
                        "🗑 Удалить",
                        style="danger",
                        callback_data=f"mod:delete:{news.id}",
                    ),
                ],
                [
                    button(
                        "⚡️ Опубликовать сразу",
                        style="success",
                        callback_data=f"mod:now:{news.id}",
                    ),
                ],
            ]

        if news.original_url and _is_public_url(news.original_url):
            rows.append([button("📄 Оригинал", url=news.original_url)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def _media_inputs(news: News, limit: int = 3) -> tuple[list[tuple[object, str]], int]:
        """Uploadable previews for the first ``limit`` photos/videos.

        Returns ``(items, total)`` where ``items`` are ``(file, type)`` pairs and
        ``total`` is how many enabled attachments the news has in total, so the
        card can say how many are only visible on the site.
        """
        import os

        from shared.config import settings
        from shared.enums import MediaType

        try:
            assets = [a for a in (news.media or []) if a.is_enabled]
        except Exception:  # noqa: BLE001 - relationship not loaded
            return [], 0

        items: list[tuple[object, str]] = []
        for asset in sorted(assets, key=lambda a: a.position or 0):
            if len(items) >= limit:
                break
            if asset.type not in (MediaType.PHOTO, MediaType.VIDEO):
                continue
            file: object | None = None
            path = asset.processed_path or asset.file_path
            if path:
                abs_path = (
                    path if os.path.isabs(path) else os.path.join(settings.media_root, path)
                )
                if os.path.exists(abs_path):
                    from aiogram.types import FSInputFile

                    file = FSInputFile(abs_path)
            if file is None and asset.telegram_file_id:
                file = asset.telegram_file_id
            if file is None and asset.remote_url:
                from aiogram.types import URLInputFile

                file = URLInputFile(asset.remote_url)
            if file is not None:
                items.append((file, "video" if asset.type == MediaType.VIDEO else "photo"))
        return items, len(assets)

    @staticmethod
    def build_card_body(
        news: News,
        city: City,
        *,
        rendered: str | None = None,
        source_name: str = "",
        moderator: str | None = None,
        tz_offset: int = 3,
        template: str | None = None,
    ) -> str:
        """Build the moderation card text.

        The post itself is shown exactly as it will be published (``rendered``
        template output). Below it we add a moderator-only info block: source
        with a link to the original, publication time at the source and the
        time AI finished processing.
        """
        from shared.services.html_sanitizer import sanitize_telegram_html

        emoji = (news.emoji or "").strip()
        title = news.title or news.original_title or ""

        if rendered:
            post = sanitize_telegram_html(rendered)
        else:
            body = news.text or news.original_text or ""
            heading = f"{emoji} <b>{title}</b>".strip() if title else ""
            post = sanitize_telegram_html(f"{heading}\n\n{body}" if heading else body)
        post = post[:2500]

        def fmt(value: object) -> str:
            """Format a timestamp in the configured display timezone."""
            if not value:
                return "—"
            try:
                from datetime import timedelta, timezone as _tz

                aware = value if value.tzinfo else value.replace(tzinfo=_tz.utc)  # type: ignore[union-attr]
                local = aware.astimezone(_tz(timedelta(hours=tz_offset)))
                return local.strftime("%d.%m.%Y %H:%M")
            except AttributeError:
                return str(value)

        # The source link lives inside the rendered post itself, so the info
        # block below only carries moderator metadata.
        score = f"{news.match_score:.0%}" if news.match_score is not None else "—"
        place = "🌍 Мировые новости" if news.is_world_news else f"🏙 {city.name}"
        info = [
            "➖➖➖➖➖",
            f"🆔 {news.id} · {place} · 🎯 {score}",
            f"🕐 В источнике: {fmt(news.source_published_at)}",
        ]
        if news.processed_at:
            info.append(f"✅ Обработано: {fmt(news.processed_at)}")
        if news.reply_to_news_id:
            info.append(f"↩️ Дополнение к новости #{news.reply_to_news_id}")
        if moderator:
            info.append(f"👤 Обработал: {moderator}")

        # Status tags, mirroring the admin panel. Shown as the bold heading
        # below, so it is NOT repeated inside the info block.
        tags = [STATUS_TAGS.get(news.status.value, news.status.value)]
        if news.is_edited:
            tags.append("✏️ изменено")
        status = " · ".join(tags)

        # Fixed built-in layout (the moderation-card template setting was
        # removed): a BOLD, UPPERCASE status heading on top, the post wrapped in
        # a Telegram <blockquote>, then the metadata block.
        status_heading = f"<b>{status.upper()}</b>"
        quoted_post = f"<blockquote>{post}</blockquote>" if post.strip() else ""
        parts = [status_heading]
        if quoted_post:
            parts.append(quoted_post)
        parts.append("\n".join(info))
        return "\n\n".join(p for p in parts if p.strip())

    async def send_moderation_card(
        self,
        news: News,
        city: City,
        lang: str = "ru",
        *,
        rendered: str | None = None,
        source_name: str = "",
        tz_offset: int = 3,
        topic_id: int | None = None,
        template: str | None = None,
    ) -> int | None:
        """Send the moderation card to a topic. Returns the message id.

        ``topic_id`` overrides the city's topic — used to route world news into
        their own dedicated topic. ``template`` is the configurable card layout
        (``settings.moderation.card_template``); ``None`` = built-in layout.
        """
        if not self.group_id:
            return None
        bot = self._bot()
        try:
            body = self.build_card_body(
                news, city, rendered=rendered, source_name=source_name, tz_offset=tz_offset,
                template=template,
            )
            common: dict = {"chat_id": self.group_id}
            thread = topic_id or city.telegram_topic_id
            if thread:
                common["message_thread_id"] = thread
            keyboard = self.build_moderation_keyboard(news, lang)

            # Show a few attachments right on the card so moderators can see
            # what will be published; the rest stay on the site to keep the
            # topic light.
            previews, total = self._media_inputs(news)
            if total > len(previews):
                body += f"\n📎 Вложений: {total}. Остальные — на сайте."
            if len(previews) > 1:
                from aiogram.types import InputMediaPhoto, InputMediaVideo

                album: list = []
                for file, kind in previews:
                    cls = InputMediaVideo if kind == "video" else InputMediaPhoto
                    album.append(cls(media=file))
                album_msgs = await bot.send_media_group(media=album, **common)
                # An album cannot carry a caption+keyboard that stay editable, so
                # the card itself is the text message replying to the previews.
                message = await bot.send_message(
                    text=body,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                    reply_to_message_id=album_msgs[0].message_id,
                    **common,
                )
            elif previews:
                file, kind = previews[0]
                send = bot.send_video if kind == "video" else bot.send_photo
                message = await send(
                    **{kind: file},
                    caption=body[:1024],
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    **common,
                )
            else:
                message = await bot.send_message(
                    text=body,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                    **common,
                )
            log.info("moderation_card_sent", news=news.id, message=message.message_id)
            return message.message_id
        except Exception as exc:  # noqa: BLE001
            log.error("moderation_card_failed", news=news.id, error=str(exc))
            return None
        finally:
            await bot.session.close()

    async def update_moderation_card(
        self,
        news: News,
        city: City,
        *,
        status_line: str,
        keep_buttons: bool = False,
        lang: str = "ru",
        rendered: str | None = None,
        source_name: str = "",
        moderator: str | None = None,
        tz_offset: int = 3,
        template: str | None = None,
    ) -> bool:
        """Rewrite an existing moderation card after a decision.

        Used to reflect approve/reject/delete on the card itself: the status and
        the moderator are appended, and the buttons are removed (or restored
        when a published post is taken down again).
        """
        if not self.group_id or not news.moderation_message_id:
            return False
        bot = self._bot()
        try:
            body = self.build_card_body(
                news, city, rendered=rendered, source_name=source_name, moderator=moderator,
                tz_offset=tz_offset, template=template,
            )
            full = f"{body}\n{status_line}"
            keyboard = self.build_moderation_keyboard(news, lang) if keep_buttons else None
            # Cards with media were sent as a photo (caption); text edits fail on
            # them, so fall back to editing the caption.
            try:
                await bot.edit_message_text(
                    chat_id=self.group_id,
                    message_id=news.moderation_message_id,
                    text=full,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
            except Exception:  # noqa: BLE001
                await bot.edit_message_caption(
                    chat_id=self.group_id,
                    message_id=news.moderation_message_id,
                    caption=full[:1024],
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("moderation_card_update_failed", news=news.id, error=str(exc))
            return False
        finally:
            await bot.session.close()
