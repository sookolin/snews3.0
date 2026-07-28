"""Advertisement publishing service (shared by the API and the scheduler)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import AdStatus, MediaType
from shared.exceptions import NotFoundError, PublishError
from shared.logging import get_logger
from shared.models.ad import Ad
from shared.models.channel import Channel
from shared.models.media import MediaAsset
from shared.models.template import Template
from shared.plugins.publishers import PublishRequest, publisher_registry
from shared.services.template_renderer import TemplateRenderer

log = get_logger("ad_publisher")


class AdPublisherService:
    """Render and deliver an advertisement to its target channel."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish(self, ad_id: int) -> Ad:
        ad = await self.session.get(Ad, ad_id)
        if ad is None:
            raise NotFoundError(f"Ad {ad_id} not found")
        if ad.channel_id is None:
            raise PublishError("У рекламы не выбран канал")
        channel = await self.session.get(Channel, ad.channel_id)
        if channel is None:
            raise PublishError("Целевой канал не найден")

        media = self._build_media(ad)
        text = await self._render_text(ad)

        publisher = publisher_registry.get("telegram")(channel)
        result = await publisher.publish(
            PublishRequest(
                text=text,
                media=media,
                is_spoiler=ad.is_spoiler,
                buttons=ad.buttons or [],
                latitude=ad.latitude,
                longitude=ad.longitude,
                location_title=ad.location_title,
                location_address=ad.location_address,
            )
        )

        if result.success:
            ad.status = AdStatus.PUBLISHED
            ad.published_at = datetime.now(timezone.utc)
            ad.published_message_ids = {channel.chat_id: result.message_ids}
            ad.error = None
        else:
            ad.status = AdStatus.FAILED
            ad.error = result.error
        await self.session.flush()
        await self.session.refresh(ad)
        if not result.success:
            raise PublishError(ad.error or "Не удалось опубликовать рекламу")
        return ad

    @staticmethod
    def _build_media(ad: Ad) -> list[MediaAsset]:
        """Create transient media assets from uploaded files and URLs."""
        media: list[MediaAsset] = []
        idx = 0
        for item in ad.media_files or []:
            try:
                mtype = MediaType(item.get("type", "photo"))
            except ValueError:
                mtype = MediaType.PHOTO
            # Per-item spoiler flag, falling back to the ad-wide flag.
            spoiler = bool(item.get("spoiler", ad.is_spoiler))
            media.append(
                MediaAsset(
                    id=-(idx + 1), news_id=0, type=mtype, file_path=item.get("path"),
                    position=idx, is_enabled=True, is_spoiler=spoiler,
                )
            )
            idx += 1
        for url in ad.media_urls or []:
            media.append(
                MediaAsset(
                    id=-(idx + 1), news_id=0, type=MediaType.PHOTO, remote_url=url,
                    position=idx, is_enabled=True, is_spoiler=ad.is_spoiler,
                )
            )
            idx += 1
        return media

    async def _render_text(self, ad: Ad) -> str:
        """Render the ad text via its template and append legal ad marking."""
        text = ad.text
        if ad.template_id:
            template = await self.session.get(Template, ad.template_id)
            if template:
                text = TemplateRenderer().render(
                    template,
                    title=ad.heading or "",
                    text=ad.text,
                    source=ad.advertiser or "",
                    city="",
                )
        elif ad.heading:
            # No template: prepend the heading in bold.
            text = f"<b>{ad.heading}</b>\n\n{text}"
        marking: list[str] = []
        if ad.advertiser:
            marking.append(f"Реклама. {ad.advertiser}")
        if ad.advertiser_inn:
            marking.append(f"ИНН {ad.advertiser_inn}")
        if ad.erid:
            marking.append(f"erid: {ad.erid}")
        if marking:
            text = f"{text}\n\n<i>{' · '.join(marking)}</i>"
        return text
