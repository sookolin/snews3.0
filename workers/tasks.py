"""Celery tasks: ingestion, publishing, scheduling, moderation, backups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from shared.database import session_scope
from shared.enums import ChannelPublishMode, NewsStatus
from shared.logging import get_logger
from shared.models.channel import Channel
from shared.models.city import City
from shared.models.news import News
from shared.models.source import Source
from shared.services.pipeline import IngestionPipeline
from shared.services.publisher_service import PublisherService
from shared.services.telegram_admin import TelegramAdminService
from workers.celery_app import celery_app, run_async

log = get_logger("worker")


@celery_app.task(name="workers.tasks.ingest_source", bind=True, max_retries=3)
def ingest_source(self, source_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Fetch & process a single source, then notify moderation for new items."""

    async def _run() -> dict:
        async with session_scope() as session:
            pipeline = IngestionPipeline(session)
            report = await pipeline.process_source(source_id)
            await session.commit()

            # Send moderation cards for the newly created pending news.
            for news_id in report.created_ids:
                await _notify_moderation(session, news_id)
            return {
                "source_id": source_id,
                "created": report.created,
                "duplicates": report.duplicates,
                "unmatched": report.unmatched,
                "errors": report.errors,
            }

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("ingest_source_failed", source=source_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60) from exc


async def _notify_moderation(session, news_id: int) -> None:  # type: ignore[no-untyped-def]
    news = await session.get(News, news_id)
    if news is None or news.city_id is None:
        return
    city = await session.get(City, news.city_id)
    if city is None:
        return
    service = TelegramAdminService()
    message_id = await service.send_moderation_card(news, city, lang=city.language)
    if message_id is not None:
        news.moderation_message_id = message_id
        await session.commit()


@celery_app.task(name="workers.tasks.notify_moderation", bind=True, max_retries=2)
def notify_moderation(self, news_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Send (or resend) a moderation card for a single news item to its topic."""

    async def _run() -> dict:
        async with session_scope() as session:
            await _notify_moderation(session, news_id)
        return {"news_id": news_id, "notified": True}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("notify_moderation_failed", news=news_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(name="workers.tasks.dispatch_due_sources")
def dispatch_due_sources() -> dict:
    """Enqueue ingestion for every active source whose interval has elapsed."""

    async def _run() -> dict:
        now = datetime.now(timezone.utc)
        dispatched = 0
        async with session_scope() as session:
            sources = (
                await session.scalars(select(Source).where(Source.is_active.is_(True)))
            ).all()
            for source in sources:
                due = source.last_checked_at is None or source.last_checked_at <= now - timedelta(
                    seconds=source.check_interval_seconds
                )
                if due:
                    ingest_source.apply_async(args=[source.id], priority=source.priority)
                    dispatched += 1
        return {"dispatched": dispatched}

    return run_async(_run())


@celery_app.task(name="workers.tasks.publish_news", bind=True, max_retries=3)
def publish_news(self, news_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Publish an approved news item to its city's channels."""

    async def _run() -> dict:
        async with session_scope() as session:
            news = await PublisherService(session).publish(news_id)
            await session.commit()
            return {"news_id": news_id, "status": news.status.value}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("publish_news_failed", news=news_id, error=str(exc))
        raise self.retry(exc=exc, countdown=120) from exc


@celery_app.task(name="workers.tasks.publish_scheduled_news")
def publish_scheduled_news() -> dict:
    """Publish scheduled news whose time has come, respecting channel windows."""

    async def _run() -> dict:
        now = datetime.now(timezone.utc)
        count = 0
        async with session_scope() as session:
            due = (
                await session.scalars(
                    select(News).where(
                        News.status == NewsStatus.SCHEDULED,
                        News.scheduled_at.is_not(None),
                        News.scheduled_at <= now,
                    )
                )
            ).all()
            for news in due:
                # Respect channels that are set to manual/draft.
                channels = (
                    await session.scalars(
                        select(Channel).where(
                            Channel.city_id == news.city_id, Channel.is_active.is_(True)
                        )
                    )
                ).all()
                if channels and all(
                    c.publish_mode in (ChannelPublishMode.MANUAL, ChannelPublishMode.DRAFT)
                    for c in channels
                ):
                    continue
                publish_news.delay(news.id)
                count += 1
        return {"scheduled_published": count}

    return run_async(_run())


@celery_app.task(name="workers.tasks.run_backup")
def run_backup() -> dict:
    """Create a database + media backup archive."""
    from workers.backup import create_backup

    return run_async(create_backup())


@celery_app.task(name="workers.tasks.cleanup_temp_media")
def cleanup_temp_media(days: int = 30) -> dict:
    """Remove downloaded media of rejected/duplicate news older than N days."""

    async def _run() -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        removed = 0
        async with session_scope() as session:
            stale = (
                await session.scalars(
                    select(News).where(
                        News.status.in_([NewsStatus.REJECTED, NewsStatus.DUPLICATE]),
                        News.created_at < cutoff,
                    )
                )
            ).all()
            for news in stale:
                await session.refresh(news, attribute_names=["media"])
                for asset in news.media:
                    removed += _delete_asset_files(asset)
            await session.commit()
        return {"files_removed": removed}

    return run_async(_run())


def _delete_asset_files(asset) -> int:  # type: ignore[no-untyped-def]
    import os

    from shared.config import settings

    count = 0
    for rel in (asset.file_path, asset.processed_path, asset.thumbnail_path):
        if not rel:
            continue
        path = rel if os.path.isabs(rel) else os.path.join(settings.media_root, rel)
        try:
            if os.path.exists(path):
                os.remove(path)
                count += 1
        except OSError:
            pass
    return count
