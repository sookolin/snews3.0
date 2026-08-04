"""Celery tasks: ingestion, publishing, scheduling, moderation, backups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from shared.database import session_scope
from shared.enums import ChannelPublishMode, NewsStatus
from shared.logging import get_logger
from shared.models.channel import Channel
from shared.models.city import City
from shared.models.news import News
from shared.models.source import Source
from shared.services.emoji_guess import guess_emoji
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
    """Send the moderation card, rendered exactly like the future post."""
    from shared.services.news_moderation import NewsModerationService

    news = await session.get(News, news_id)
    if news is None or news.city_id is None:
        return
    city = await session.get(City, news.city_id)
    if city is None:
        return
    # Media must be loaded so the card can preview the first attachment.
    await session.refresh(news, attribute_names=["media"])

    from shared.services.settings_service import SettingsService

    settings_service = SettingsService(session)
    tz_offset = int(await settings_service.get("ui.timezone_offset_hours", 3))
    # World news go into their own dedicated topic when configured.
    world_topic = int(await settings_service.get("telegram.world_topic_id", 0))
    topic_override = world_topic if (news.is_world_news and world_topic) else None

    helper = NewsModerationService(session)
    service = TelegramAdminService()
    message_id = await service.send_moderation_card(
        news,
        city,
        lang=city.language,
        rendered=await helper.render(news),
        source_name=await helper.resolve_source_name(news),
        tz_offset=tz_offset,
        topic_id=topic_override,
        template=(await settings_service.get("moderation.card_template", "")) or None,
    )
    if message_id is not None:
        news.moderation_message_id = message_id
        await session.commit()

    # Web Push to everyone who asked to hear about new items on moderation.
    from shared.services.push_service import PushService

    await PushService(session).broadcast(
        "news_pending",
        "Новость на модерации",
        (news.title or news.original_title or "Без заголовка")[:120],
        url=f"/news/{news.id}",
    )


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


@celery_app.task(name="workers.tasks.process_submission", bind=True, max_retries=2)
def process_submission(self, news_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Run AI rewrite on a user-submitted news item, then send moderation card."""

    async def _run() -> dict:
        from shared.enums import NewsStatus
        from shared.services.ai_service import AIService

        async with session_scope() as session:
            news = await session.get(News, news_id)
            if news is None:
                return {"news_id": news_id, "skipped": True}
            # AI rewrite (best-effort; keep original on failure).
            try:
                result, profile = await AIService(session).process(
                    news.original_title, news.original_text
                )
                news.title = result.title or news.original_title
                news.text = result.text or news.original_text
                news.ai_profile_id = profile.id
                news.emoji = result.emoji or guess_emoji(news.title, news.text or "")
                if result.embedding:
                    news.embedding = result.embedding
            except Exception as exc:  # noqa: BLE001
                log.warning("submission_ai_failed", news=news_id, error=str(exc))
                news.title = news.original_title
                news.text = news.original_text
                if not news.emoji:
                    news.emoji = guess_emoji(news.original_title, news.original_text or "")
            news.status = NewsStatus.PENDING
            await session.commit()
            await _notify_moderation(session, news_id)
        return {"news_id": news_id, "processed": True}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("process_submission_failed", news=news_id, error=str(exc))
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


async def _schedule_publication(session, news: News) -> str:  # type: ignore[no-untyped-def]
    """Queue a news item for publication, spacing posts apart.

    Approving several items at once should not dump them all into the channel:
    each new item is scheduled ``pipeline.publish_interval_minutes`` after the
    last already-queued one. Items flagged ``publish_immediately`` jump the
    queue and go out at once.
    """
    from shared.enums import NewsStatus
    from shared.services.settings_service import SettingsService

    if news.publish_immediately:
        news.scheduled_at = None
        news.status = NewsStatus.APPROVED
        publish_news.delay(news.id)
        return "immediate"

    interval = int(
        await SettingsService(session).get("pipeline.publish_interval_minutes", 5)
    )
    if interval <= 0:
        news.scheduled_at = None
        news.status = NewsStatus.APPROVED
        publish_news.delay(news.id)
        return "immediate"

    now = datetime.now(timezone.utc)
    gap = timedelta(minutes=interval)

    # The next free slot must clear both the pending queue and the most recent
    # actual publication, otherwise a burst of approvals would all go at once.
    last_scheduled = await session.scalar(
        select(func.max(News.scheduled_at)).where(
            News.status == NewsStatus.SCHEDULED,
            News.scheduled_at.is_not(None),
            News.scheduled_at >= now,
        )
    )
    last_published = await session.scalar(
        select(func.max(News.published_at)).where(News.published_at.is_not(None))
    )
    # Also consider items just approved for immediate publication whose publish
    # task may still be in flight (published_at not written yet). Only recent
    # ones matter: an approval older than one gap no longer constrains spacing,
    # so a queue that has cooled down lets the next post go out immediately
    # ("first immediate, then every N minutes"). Using processed_at without this
    # recency bound made stale approvals randomly push slots to +2×gap.
    last_dispatched = await session.scalar(
        select(func.max(News.processed_at)).where(
            News.status == NewsStatus.APPROVED,
            News.processed_at.is_not(None),
            News.processed_at >= now - gap,
            News.id != news.id,
        )
    )

    def aware(value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    last_scheduled = aware(last_scheduled)
    last_published = aware(last_published)
    last_dispatched = aware(last_dispatched)

    candidates = [now]
    for marker in (last_scheduled, last_published, last_dispatched):
        if marker:
            candidates.append(marker + gap)
    slot = max(candidates)

    # Nothing published recently and queue empty → publish right away.
    if slot <= now:
        news.scheduled_at = None
        news.status = NewsStatus.APPROVED
        publish_news.delay(news.id)
        return "immediate"

    news.scheduled_at = slot
    news.status = NewsStatus.SCHEDULED
    log.info(
        "publication_scheduled",
        news=news.id,
        interval_min=interval,
        minutes_ahead=round((slot - now).total_seconds() / 60, 1),
        last_scheduled=str(last_scheduled),
        last_published=str(last_published),
        last_dispatched=str(last_dispatched),
    )
    return slot.strftime("%H:%M")


async def _refresh_card_after_publish(session, news: News) -> None:  # type: ignore[no-untyped-def]
    """Update the moderation card after a successful publication.

    Keeps the buttons — they are rebuilt from the fresh status, so a published
    item shows "снять с публикации" instead of "одобрить".
    """
    import contextlib

    if news is None or not news.moderation_message_id:
        return
    with contextlib.suppress(Exception):
        from shared.services.news_moderation import NewsModerationService

        line = (
            "📤 Опубликовано"
            if news.status == NewsStatus.PUBLISHED
            else f"⚠️ Ошибка публикации: {(news.error or '')[:120]}"
        )
        await NewsModerationService(session).update_card(
            news, status_line=line, keep_buttons=True
        )
        await session.commit()

    with contextlib.suppress(Exception):
        from shared.services.push_service import PushService

        published = news.status == NewsStatus.PUBLISHED
        await PushService(session).broadcast(
            "news_published" if published else "news_failed",
            "Новость опубликована" if published else "Ошибка публикации",
            (news.title or news.original_title or "Без заголовка")[:120],
            url=f"/news/{news.id}",
        )


@celery_app.task(name="workers.tasks.publish_news", bind=True, max_retries=3)
def publish_news(self, news_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Publish an approved news item to its city's channels."""

    async def _run() -> dict:
        async with session_scope() as session:
            news = await PublisherService(session).publish(news_id)
            await session.commit()
            # Refresh the moderation card so it switches to the published button
            # set (снять с публикации / удалить полностью) instead of keeping the
            # pre-decision buttons.
            await _refresh_card_after_publish(session, news)
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


@celery_app.task(name="workers.tasks.publish_scheduled_ads")
def publish_scheduled_ads() -> dict:
    """Publish ads whose recurring schedule matches the current time."""

    async def _run() -> dict:
        from shared.enums import AdStatus
        from shared.models.ad import Ad

        now = datetime.now(timezone.utc)
        hhmm = now.strftime("%H:%M")
        weekday = now.isoweekday()  # 1=Mon .. 7=Sun
        day = now.day
        published = 0

        async with session_scope() as session:
            ads = (
                await session.scalars(
                    select(Ad).where(
                        Ad.auto_publish.is_(True),
                        Ad.status.in_([AdStatus.DRAFT, AdStatus.SCHEDULED]),
                    )
                )
            ).all()
            for ad in ads:
                sched = ad.schedule or {}
                times = sched.get("times") or []
                if times and hhmm not in times:
                    continue
                weekdays = sched.get("weekdays") or []
                if weekdays and weekday not in weekdays:
                    continue
                parity = (sched.get("day_parity") or "any").lower()
                if parity == "even" and day % 2 != 0:
                    continue
                if parity == "odd" and day % 2 == 0:
                    continue
                date_from = sched.get("date_from")
                date_to = sched.get("date_to")
                today = now.strftime("%Y-%m-%d")
                if date_from and today < date_from:
                    continue
                if date_to and today > date_to:
                    continue
                publish_ad_task.delay(ad.id)
                published += 1
        return {"ads_enqueued": published}

    return run_async(_run())


@celery_app.task(name="workers.tasks.publish_ad_task", bind=True, max_retries=2)
def publish_ad_task(self, ad_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Publish a single ad (used by the scheduler)."""

    async def _run() -> dict:
        from shared.services.ad_publisher import AdPublisherService

        async with session_scope() as session:
            ad = await AdPublisherService(session).publish(ad_id)
            await session.commit()
            return {"ad_id": ad_id, "status": ad.status.value}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("publish_ad_failed", ad=ad_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60) from exc


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
                        News.status.in_([NewsStatus.REJECTED, NewsStatus.FAILED]),
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


@celery_app.task(name="workers.tasks.send_daily_digests")
def send_daily_digests() -> dict:  # type: ignore[no-untyped-def]
    """Send Telegram DM digests to users whose configured hour matches now."""

    async def _run() -> dict:
        async with session_scope() as session:
            from shared.services.bot_notify import BotNotifyService

            sent = await BotNotifyService(session).send_daily_digests()
        return {"sent": sent}

    return run_async(_run())


def _parse_hhmm(value: str | None) -> int | None:
    """Parse ``"HH:MM"`` into minutes-since-midnight, tolerant of stray input.

    Accepts values with or without leading zeros (``9:5`` → 545). Returns
    ``None`` when the value is missing or not a valid time.
    """
    if not value:
        return None
    try:
        hh, mm = value.strip().split(":", 1)
        h, m = int(hh), int(mm)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


async def _render_weather(session, city, channel, body: str) -> str:
    """Render the weather body through the template bound to this channel/city.

    Uses the SAME precedence as normal publishing so the weather post looks like
    every other post of the city:
        channel.template_id → city.template_id → default → any.
    Also passes ``link`` = the channel's public t.me link, so a ``{link}``
    hyperlink in the template's footer actually resolves.
    """
    from shared.models.template import Template
    from shared.services.publisher_service import channel_subscribe_link
    from shared.services.template_renderer import TemplateRenderer

    template = None
    if getattr(channel, "template_id", None):
        template = await session.get(Template, channel.template_id)
    if template is None and getattr(city, "template_id", None):
        template = await session.get(Template, city.template_id)
    if template is None:
        template = await session.scalar(
            select(Template).where(Template.is_default.is_(True)).limit(1)
        )
    if template is None:
        template = await session.scalar(select(Template).limit(1))
    if template is None:
        return body
    return TemplateRenderer().render(
        template,
        title=f"Погода в городе {city.name}",
        text=body,
        city=city.name,
        link=channel_subscribe_link(channel),
    )

async def _publish_weather_for_city(session, city) -> int:
    """Fetch the forecast and post it to every active channel of *city*."""
    from shared.models.channel import Channel
    from shared.plugins.publishers import PublishRequest, publisher_registry
    from shared.services import weather_service

    lat, lon = city.weather_lat, city.weather_lon
    if lat is None or lon is None:
        coords = await weather_service._geocode(city.name)
        if coords is None:
            return 0
        lat, lon = coords
        city.weather_lat, city.weather_lon = lat, lon
        await session.flush()

    forecast = await weather_service.fetch_forecast(lat, lon)
    if forecast is None:
        return 0

    # Skip parts of the day already in the past (rest-of-day summary when
    # published in the evening). Uses the UI timezone offset for 'now'.
    from shared.services.settings_service import SettingsService
    tz_offset = int(await SettingsService(session).get('ui.timezone_offset_hours', 3))
    now_local = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
    body = weather_service.format_post(city.name, forecast, from_hour=now_local.hour)
    if not body.strip():
        body = weather_service.format_post(city.name, forecast, from_hour=0)

    channels = (
        await session.scalars(
            select(Channel).where(Channel.city_id == city.id, Channel.is_active.is_(True))
        )
    ).all()
    publisher_cls = publisher_registry.get("telegram")
    sent = 0
    for channel in channels:
        # Render per channel so each uses its bound template and its own {link}.
        text = await _render_weather(session, city, channel, body)
        try:
            result = await publisher_cls(channel).publish(PublishRequest(text=text))
            if result.success:
                sent += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("weather_publish_failed", city=city.id, channel=channel.id, error=str(exc))
    return sent


@celery_app.task(name="workers.tasks.publish_city_weather")
def publish_city_weather() -> dict:
    """Publish the daily weather post to cities whose configured time is now."""

    async def _run() -> dict:
        from shared.models.city import City
        from shared.services.settings_service import SettingsService

        # Tolerance (minutes): the beat tick fires every 60s but can drift or be
        # delayed in the queue, so an exact "HH:MM == now" match would silently
        # skip the minute and never publish. Publish when the current local time
        # is within this many minutes AT OR AFTER the configured time, guarded by
        # a once-per-day marker so the window never double-posts.
        window_minutes = 5

        published = 0
        async with session_scope() as session:
            tz_offset = int(await SettingsService(session).get("ui.timezone_offset_hours", 3))
            now_local = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
            today = now_local.strftime("%Y-%m-%d")
            now_minutes = now_local.hour * 60 + now_local.minute

            cities = (
                await session.scalars(
                    select(City).where(
                        City.is_active.is_(True),
                        City.weather_enabled.is_(True),
                        City.weather_time.is_not(None),
                    )
                )
            ).all()
            for city in cities:
                # Already posted today → skip (idempotent within the window).
                if city.weather_last_published_on == today:
                    continue
                target = _parse_hhmm(city.weather_time)
                if target is None:
                    continue
                # Fire when now is in [target, target + window]. Catches a missed
                # exact minute without re-firing before the scheduled time.
                if not (target <= now_minutes <= target + window_minutes):
                    continue
                sent = await _publish_weather_for_city(session, city)
                # Mark the day as done even if there were no channels/forecast,
                # so a misconfigured city is not retried every minute all day.
                city.weather_last_published_on = today
                published += sent
            await session.commit()
        return {"weather_posts": published}

    return run_async(_run())


@celery_app.task(name="workers.tasks.publish_city_weather_now", bind=True, max_retries=1)
def publish_city_weather_now(self, city_id: int) -> dict:  # type: ignore[no-untyped-def]
    """Publish the weather post for one city immediately (manual test button).

    Ignores the schedule and the once-per-day marker so an operator can verify
    the forecast and channel wiring on demand.
    """

    async def _run() -> dict:
        from shared.models.city import City

        async with session_scope() as session:
            city = await session.get(City, city_id)
            if city is None:
                return {"city_id": city_id, "error": "not_found", "sent": 0}
            sent = await _publish_weather_for_city(session, city)
            await session.commit()
        return {"city_id": city_id, "sent": sent}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        log.error("weather_now_failed", city=city_id, error=str(exc))
        raise self.retry(exc=exc, countdown=15) from exc
