"""News versioning service — snapshot history & rollback."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.exceptions import NotFoundError
from shared.models.news import News, NewsVersion


class VersionService:
    """Create immutable snapshots of news items and restore them."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(
        self, news: News, *, edited_by: int | None = None, comment: str | None = None
    ) -> NewsVersion:
        """Store the current state of ``news`` as a new version."""
        next_version = (
            await self.session.scalar(
                select(func.coalesce(func.max(NewsVersion.version), 0)).where(
                    NewsVersion.news_id == news.id
                )
            )
            or 0
        ) + 1

        version = NewsVersion(
            news_id=news.id,
            version=next_version,
            title=news.title,
            text=news.text,
            snapshot={
                "original_title": news.original_title,
                "original_text": news.original_text,
                "title": news.title,
                "text": news.text,
                "city_id": news.city_id,
                "template_id": news.template_id,
                "is_spoiler": news.is_spoiler,
                "apply_watermark": news.apply_watermark,
                "status": news.status.value,
            },
            edited_by=edited_by,
            comment=comment,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def list_versions(self, news_id: int) -> list[NewsVersion]:
        return list(
            (
                await self.session.scalars(
                    select(NewsVersion)
                    .where(NewsVersion.news_id == news_id)
                    .order_by(NewsVersion.version.desc())
                )
            ).all()
        )

    async def restore(self, news_id: int, version: int, *, edited_by: int | None = None) -> News:
        """Roll a news item back to a previous version (snapshotting current first)."""
        news = await self.session.get(News, news_id)
        if news is None:
            raise NotFoundError(f"News {news_id} not found")

        target = await self.session.scalar(
            select(NewsVersion).where(
                NewsVersion.news_id == news_id, NewsVersion.version == version
            )
        )
        if target is None:
            raise NotFoundError(f"Version {version} not found for news {news_id}")

        # Snapshot current state before overwriting so rollback is itself reversible.
        await self.snapshot(news, edited_by=edited_by, comment=f"before restore v{version}")

        snap = target.snapshot
        news.title = snap.get("title")
        news.text = snap.get("text")
        news.template_id = snap.get("template_id")
        news.is_spoiler = bool(snap.get("is_spoiler", news.is_spoiler))
        news.apply_watermark = bool(snap.get("apply_watermark", news.apply_watermark))
        await self.session.flush()
        return news
