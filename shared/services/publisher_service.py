"""Publisher service — renders templates and dispatches to channels.

Handles the full publish flow for an approved news item: choose the template,
render text per channel, apply watermark to media, then publish via the
appropriate publisher plugin for each of the city's active channels.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import NewsStatus
from shared.exceptions import NotFoundError, PublishError
from shared.logging import get_logger
from shared.models.channel import Channel
from shared.models.news import News
from shared.models.source import Source
from shared.models.template import Template
from shared.plugins.publishers import PublishRequest, publisher_registry
from shared.services.media_service import MediaService
from shared.services.template_renderer import TemplateRenderer

log = get_logger("publisher_service")


def channel_subscribe_link(channel: Channel) -> str:
    """Public t.me link for a channel, used for the ``{link}`` placeholder.

    Prefers the channel's ``@username``; falls back to a ``t.me/c/<id>`` link
    for private channels, and to an empty string when neither is known (the
    template's own ``subscribe_link`` then applies).
    """
    username = (channel.username or "").strip().lstrip("@")
    if not username:
        raw = (channel.chat_id or "").strip()
        if raw and not raw.lstrip("-").isdigit():
            username = raw.lstrip("@").rstrip("/").rsplit("/", 1)[-1]
    if username:
        return f"https://t.me/{username}"

    raw_id = (channel.chat_id or "").strip()
    if raw_id.startswith("-100") and raw_id[4:].isdigit():
        return f"https://t.me/c/{raw_id[4:]}"
    return ""


class PublisherService:
    """Publish approved news to their city's Telegram channels."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.renderer = TemplateRenderer()
        self.media_service = MediaService(session)

    async def _resolve_template(self, news: News) -> Template:
        template: Template | None = None
        if news.template_id:
            template = await self.session.get(Template, news.template_id)
        # Fall back to the city's own template (bound at city creation). Load the
        # city by id if the relationship is not populated, so this works even
        # when the caller did not eager-load ``news.city``.
        if template is None and news.city_id:
            city = news.city
            if city is None:
                from shared.models.city import City

                city = await self.session.get(City, news.city_id)
            if city and city.template_id:
                template = await self.session.get(Template, city.template_id)
        if template is None:
            template = await self.session.scalar(
                select(Template)
                .where(Template.is_default.is_(True), Template.is_active.is_(True))
                .limit(1)
            )
        if template is None:
            template = await self.session.scalar(select(Template).limit(1))
        if template is None:
            raise NotFoundError("No publication template configured")
        return template

    async def publish(self, news_id: int, city_ids: list[int] | None = None) -> News:
        """Publish a single news item. Returns the updated ``News``.

        ``city_ids``, when given, restricts this call to only the channels of
        those target cities — used for partial approval, where a moderator
        with restricted city access approves/publishes only their accessible
        cities while the item stays pending for the rest. Already-published
        channels are never re-published; the item's ``published_message_ids``
        accumulate across calls and the status only becomes ``PUBLISHED`` once
        every target city's channels have been covered.
        """
        news = await self.session.get(News, news_id)
        if news is None:
            raise NotFoundError(f"News {news_id} not found")
        if news.city_id is None:
            raise PublishError("Нельзя публиковать новость без города")

        # Ensure relationships are loaded.
        await self.session.refresh(news, attribute_names=["media", "city", "target_cities"])

        # Publish to the channels of EVERY target city (multi-channel post),
        # falling back to just the primary city for legacy items with no
        # explicit targets.
        all_target_city_ids = [c.id for c in (news.target_cities or [])] or [news.city_id]
        # This call only touches the requested subset (default: all targets).
        call_city_ids = (
            [cid for cid in city_ids if cid in all_target_city_ids]
            if city_ids is not None
            else all_target_city_ids
        )
        if not call_city_ids:
            raise PublishError("Нет доступных для публикации городов")

        already_published_chats = set((news.published_message_ids or {}).keys())

        channels = (
            await self.session.scalars(
                select(Channel).where(
                    Channel.city_id.in_(call_city_ids), Channel.is_active.is_(True)
                )
            )
        ).all()
        # Never republish a channel that already has a live message for this
        # news (double-publication guard, now scoped per channel instead of
        # the whole item so partial approval keeps working).
        channels = [c for c in channels if c.chat_id not in already_published_chats]
        if not channels:
            if already_published_chats:
                # Everything requested is already live — nothing to do, but
                # this is not an error (e.g. re-approving the same cities).
                return news
            raise PublishError("У целевых городов нет активных каналов")

        # Map city_id → City for per-channel template + {city} placeholder.
        from shared.models.city import City as _City

        cities_by_id = {
            c.id: c
            for c in (
                await self.session.scalars(select(_City).where(_City.id.in_(all_target_city_ids)))
            ).all()
        }

        # Follow-up threading: reply to the parent news' message per chat.
        reply_map: dict[str, int] = {}
        if news.reply_to_news_id:
            parent = await self.session.get(News, news.reply_to_news_id)
            if parent and parent.published_message_ids:
                for chat_id, ids in (parent.published_message_ids or {}).items():
                    if ids:
                        reply_map[str(chat_id)] = ids[0]

        # Source: manual override wins, then the linked Source name; can be
        # hidden entirely per post.
        source_name = ""
        # Manual link override wins; hidden source means no link at all.
        source_url = (
            "" if news.hide_source
            else (news.source_url_override or news.original_url or "")
        )
        if not news.hide_source:
            if news.source_name:
                source_name = news.source_name
            elif news.source_id:
                source = await self.session.get(Source, news.source_id)
                if source and source.show_in_post:
                    source_name = source.name

        # Author: show the author name unless it was explicitly hidden.
        author_name = "" if news.submitted_anonymously else (news.author_name or "")

        # Resolve which watermark profile to use: the target channel's bound
        # profile wins, else the default active one. Media is processed once and
        # reused across channels, so for a multi-channel post the primary
        # channel's watermark is applied. ``channels`` is ordered by the query;
        # pick the one for the primary city first for a stable choice.
        wm_profile = None
        try:
            from shared.models.watermark import WatermarkProfile as _WM

            primary_channel = next(
                (c for c in channels if c.city_id == news.city_id), channels[0]
            )
            if getattr(primary_channel, "watermark_id", None):
                wm_profile = await self.session.get(_WM, primary_channel.watermark_id)
        except Exception:  # noqa: BLE001 - never fail publish over watermark lookup
            wm_profile = None

        # Process media (watermark) once.
        for asset in news.media:
            # Re-process when nothing was produced yet, or when a previous run
            # skipped watermarking (processed == original) but it is now wanted.
            needs_processing = asset.processed_path is None or (
                news.apply_watermark and asset.processed_path == asset.file_path
            )
            if needs_processing:
                await self.media_service.process_asset(
                    asset, apply_watermark=news.apply_watermark, profile=wm_profile
                )

        # Load global tags from settings once per publish call.
        global_tags: list[dict] = []
        try:
            import json as _json
            from shared.services.settings_service import SettingsService
            _raw = await SettingsService(self.session).get("templates.global_tags", "") or ""
            if isinstance(_raw, str) and _raw.strip().startswith("["):
                global_tags = _json.loads(_raw)
            elif isinstance(_raw, list):
                global_tags = _raw
        except Exception:
            pass

        published: dict[str, list[int]] = {}
        errors: list[str] = []

        for channel in channels:
            channel_city = cities_by_id.get(channel.city_id)
            # Template precedence per channel: channel override → channel city's
            # own template → news template → global default. This is what makes
            # each city's post use the template bound to that city.
            template = None
            if channel.template_id:
                template = await self.session.get(Template, channel.template_id)
            if template is None and channel_city and channel_city.template_id:
                template = await self.session.get(Template, channel_city.template_id)
            if template is None:
                template = await self._resolve_template(news)

            text = self.renderer.render(
                template,
                title=news.title or news.original_title or "",
                text=news.text or news.original_text,
                source=source_name,
                source_url=source_url,
                city=channel_city.name if channel_city else (news.city.name if news.city else ""),
                author=author_name,
                emoji=news.emoji or "",
                published_at=datetime.now(timezone.utc),
                # {link} points at the channel this copy is published to, so one
                # template serves every city.
                link=channel_subscribe_link(channel),
                global_tags=global_tags,
            )

            publisher_cls = publisher_registry.get("telegram")
            publisher = publisher_cls(channel)
            result = await publisher.publish(
                PublishRequest(
                    text=text,
                    media=list(news.media),
                    disable_web_preview=template.disable_web_preview,
                    is_spoiler=news.is_spoiler,
                    latitude=news.latitude,
                    longitude=news.longitude,
                    location_title=news.location_title,
                    location_address=news.location_address,
                    buttons=news.buttons or [],
                    reply_to_message_id=reply_map.get(str(channel.chat_id)),
                )
            )
            if result.success:
                published[channel.chat_id] = result.message_ids
            else:
                errors.append(f"{channel.title}: {result.error}")

        # Merge into whatever was already published (previous partial-approval
        # calls for other target cities), instead of overwriting it.
        merged = dict(news.published_message_ids or {})
        merged.update(published)
        news.published_message_ids = merged

        # Track which target cities are now covered so the item is only
        # considered fully PUBLISHED once every target city's channels have
        # received it. Cities with no active channel count as covered so they
        # never block completion.
        approved = set(news.approved_city_ids or [])
        approved.update(call_city_ids)
        news.approved_city_ids = sorted(approved)

        covered_chat_ids = set(merged.keys())
        all_channels = (
            await self.session.scalars(
                select(Channel).where(
                    Channel.city_id.in_(all_target_city_ids), Channel.is_active.is_(True)
                )
            )
        ).all()
        remaining = [c for c in all_channels if c.chat_id not in covered_chat_ids]

        if published:
            news.published_at = datetime.now(timezone.utc)
            news.error = "; ".join(errors) if errors else None
            # PUBLISHED as soon as it is live somewhere — a super admin (full
            # access) still sees the remaining target cities and can approve
            # them to finish the rollout to every channel.
            news.status = NewsStatus.PUBLISHED
        elif not merged:
            news.status = NewsStatus.FAILED
            news.error = "; ".join(errors) or "No channels published"
            await self.session.flush()
            raise PublishError(news.error)

        await self.session.flush()
        log.info(
            "news_published",
            news=news.id,
            channels=len(published),
            remaining_cities=[c.city_id for c in remaining],
        )
        return news
