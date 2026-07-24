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
        if template is None and news.city and news.city.template_id:
            template = await self.session.get(Template, news.city.template_id)
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

    async def publish(self, news_id: int) -> News:
        """Publish a single news item. Returns the updated ``News``."""
        news = await self.session.get(News, news_id)
        if news is None:
            raise NotFoundError(f"News {news_id} not found")
        if news.city_id is None:
            raise PublishError("Cannot publish news without a city")

        # Ensure relationships are loaded.
        await self.session.refresh(news, attribute_names=["media", "city"])

        channels = (
            await self.session.scalars(
                select(Channel).where(Channel.city_id == news.city_id, Channel.is_active.is_(True))
            )
        ).all()
        if not channels:
            raise PublishError("City has no active channels")

        source_name = ""
        source_url = news.original_url or ""
        if news.source_id:
            source = await self.session.get(Source, news.source_id)
            if source:
                source_name = source.name

        # Process media (watermark) once.
        for asset in news.media:
            if asset.processed_path is None:
                await self.media_service.process_asset(asset, apply_watermark=news.apply_watermark)

        published: dict[str, list[int]] = {}
        errors: list[str] = []

        for channel in channels:
            template = (
                await self.session.get(Template, channel.template_id)
                if channel.template_id
                else await self._resolve_template(news)
            )
            if template is None:
                template = await self._resolve_template(news)

            text = self.renderer.render(
                template,
                title=news.title or news.original_title or "",
                text=news.text or news.original_text,
                source=source_name,
                source_url=source_url,
                city=news.city.name if news.city else "",
                published_at=datetime.now(timezone.utc),
            )

            publisher_cls = publisher_registry.get("telegram")
            publisher = publisher_cls(channel)
            result = await publisher.publish(
                PublishRequest(
                    text=text,
                    media=list(news.media),
                    disable_web_preview=template.disable_web_preview,
                    is_spoiler=news.is_spoiler,
                )
            )
            if result.success:
                published[channel.chat_id] = result.message_ids
            else:
                errors.append(f"{channel.title}: {result.error}")

        news.published_message_ids = published
        if published:
            news.status = NewsStatus.PUBLISHED
            news.published_at = datetime.now(timezone.utc)
            news.error = "; ".join(errors) if errors else None
        else:
            news.status = NewsStatus.FAILED
            news.error = "; ".join(errors) or "No channels published"
            raise PublishError(news.error)

        await self.session.flush()
        log.info("news_published", news=news.id, channels=len(published))
        return news
