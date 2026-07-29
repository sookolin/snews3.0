"""Dashboard statistics & system monitoring endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select

from backend.app.deps import DBSession, require_permission
from shared.enums import NewsOrigin, NewsStatus, Permission
from shared.models.channel import Channel
from shared.models.city import City
from shared.models.news import News
from shared.models.source import Source
from shared.models.user import User
from shared.schemas.dashboard import (
    DashboardStats,
    HourPoint,
    ServiceHealth,
    SourceStat,
    StatusCount,
    SystemStatus,
    TimeSeriesPoint,
)

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> DashboardStats:
    """Aggregate statistics for the dashboard."""

    async def count_status(status: NewsStatus) -> int:
        return (
            await session.scalar(
                select(func.count()).select_from(News).where(News.status == status)
            )
            or 0
        )

    total_news = await session.scalar(select(func.count()).select_from(News)) or 0
    total_cities = await session.scalar(select(func.count()).select_from(City)) or 0
    total_sources = await session.scalar(select(func.count()).select_from(Source)) or 0
    active_sources = (
        await session.scalar(
            select(func.count()).select_from(Source).where(Source.is_active.is_(True))
        )
        or 0
    )
    total_channels = await session.scalar(select(func.count()).select_from(Channel)) or 0
    active_channels = (
        await session.scalar(
            select(func.count()).select_from(Channel).where(Channel.is_active.is_(True))
        )
        or 0
    )
    # Source throughput over the last 30 days: volume plus how much of it
    # actually reached a channel. More actionable than a channel headcount.
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    published_case = func.sum(
        case((News.status == NewsStatus.PUBLISHED, 1), else_=0)
    )
    top_source_rows = (
        await session.execute(
            select(Source.name, func.count(News.id), published_case)
            .join(News, News.source_id == Source.id)
            .where(News.created_at >= month_ago)
            .group_by(Source.id, Source.name)
            .order_by(func.count(News.id).desc())
            .limit(8)
        )
    ).all()
    top_sources = [
        SourceStat(name=name, total=total or 0, published=int(published or 0))
        for name, total, published in top_source_rows
    ]

    # Publications by hour of day — shows when the feed is busiest.
    hour_rows = (
        await session.execute(
            select(
                func.extract("hour", News.published_at).label("hour"),
                func.count(),
            )
            .where(News.published_at.is_not(None), News.published_at >= month_ago)
            .group_by("hour")
        )
    ).all()
    hour_counts = {int(h): c for h, c in hour_rows if h is not None}
    by_hour = [HourPoint(hour=h, count=hour_counts.get(h, 0)) for h in range(24)]

    # Average time from ingest to publication, in minutes.
    avg_seconds = await session.scalar(
        select(
            func.avg(
                func.extract("epoch", News.published_at - News.created_at)
            )
        ).where(News.published_at.is_not(None), News.published_at >= month_ago)
    )
    avg_moderation_minutes = round(float(avg_seconds or 0) / 60, 1)

    # Bot usage statistics (news submitted by Telegram users).
    bot_submissions = (
        await session.scalar(
            select(func.count()).select_from(News).where(News.origin == NewsOrigin.USER)
        )
        or 0
    )
    bot_unique_users = (
        await session.scalar(
            select(func.count(func.distinct(News.submitted_by_telegram_id))).where(
                News.submitted_by_telegram_id.is_not(None)
            )
        )
        or 0
    )
    bot_anonymous = (
        await session.scalar(
            select(func.count())
            .select_from(News)
            .where(News.submitted_anonymously.is_(True))
        )
        or 0
    )

    by_status_rows = (
        await session.execute(select(News.status, func.count()).group_by(News.status))
    ).all()
    by_status = [StatusCount(status=str(s.value), count=c) for s, c in by_status_rows]

    # Last 7 days published counts.
    since = datetime.now(timezone.utc) - timedelta(days=7)
    daily_rows = (
        await session.execute(
            select(func.date(News.created_at), func.count())
            .where(News.created_at >= since)
            .group_by(func.date(News.created_at))
            .order_by(func.date(News.created_at))
        )
    ).all()
    last_7 = [TimeSeriesPoint(date=str(d), count=c) for d, c in daily_rows]

    return DashboardStats(
        total_news=total_news,
        published=await count_status(NewsStatus.PUBLISHED),
        pending=await count_status(NewsStatus.PENDING),
        rejected=await count_status(NewsStatus.REJECTED),
        failed=await count_status(NewsStatus.FAILED),
        duplicates=0,  # duplicates are skipped at ingest, never stored
        total_cities=total_cities,
        active_sources=active_sources,
        total_sources=total_sources,
        total_channels=total_channels,
        active_channels=active_channels,
        top_sources=top_sources,
        by_hour=by_hour,
        avg_moderation_minutes=avg_moderation_minutes,
        bot_submissions=bot_submissions,
        bot_unique_users=bot_unique_users,
        bot_anonymous=bot_anonymous,
        by_status=by_status,
        last_7_days=last_7,
    )


@router.get("/system", response_model=SystemStatus)
async def system_status(
    session: DBSession,
    _: User = Depends(require_permission(Permission.MONITORING_VIEW)),
) -> SystemStatus:
    """Health of dependent services + host resource usage + queue depth."""
    services: list[ServiceHealth] = []

    # Database
    try:
        await session.execute(select(1))
        services.append(ServiceHealth(name="postgres", healthy=True))
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceHealth(name="postgres", healthy=False, detail=str(exc)))

    # Redis + queue depth. No task_routes are configured and the worker starts
    # without -Q, so every task lands on the default "celery" list. The extra
    # names are kept as a cheap safety net in case routing is added later.
    queue_depth = 0
    try:
        from shared.redis_client import get_redis

        redis = get_redis()
        await redis.ping()
        for queue in ("celery", "ingest", "publish", "ai", "media", "maintenance"):
            try:
                queue_depth += int(await redis.llen(queue) or 0)
            except Exception:  # noqa: BLE001 - key of another type / missing
                continue
        services.append(ServiceHealth(name="redis", healthy=True))
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceHealth(name="redis", healthy=False, detail=str(exc)))

    # Celery workers. inspect() is blocking, so it runs in a thread to avoid
    # stalling the event loop for the whole timeout.
    active_workers = 0
    running_tasks = 0
    worker_names: list[str] = []
    try:
        import asyncio

        from workers.celery_app import celery_app

        def _inspect() -> tuple[dict, dict, dict]:
            inspector = celery_app.control.inspect(timeout=1.5)
            return (
                inspector.ping() or {},
                inspector.active() or {},
                inspector.reserved() or {},
            )

        pong, active, reserved = await asyncio.to_thread(_inspect)
        worker_names = sorted(pong)
        active_workers = len(worker_names)
        running_tasks = sum(len(v or []) for v in active.values()) + sum(
            len(v or []) for v in reserved.values()
        )
        services.append(
            ServiceHealth(
                name="celery",
                healthy=active_workers > 0,
                detail=None if active_workers else "воркеры не отвечают на ping",
            )
        )
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceHealth(name="celery", healthy=False, detail=str(exc)))

    # Host resources. psutil is a hard dependency now; keep the guard so a
    # partial install degrades with an explanation instead of silent zeros.
    cpu_percent = 0.0
    memory_percent = 0.0
    resources_detail: str | None = None
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
    except Exception as exc:  # noqa: BLE001
        resources_detail = f"psutil недоступен: {exc}"

    # Pipeline counters from the database — always populated.
    async def _count(*conditions) -> int:  # type: ignore[no-untyped-def]
        stmt = select(func.count()).select_from(News)
        for cond in conditions:
            stmt = stmt.where(cond)
        return await session.scalar(stmt) or 0

    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    return SystemStatus(
        services=services,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        queue_depth=queue_depth,
        active_workers=active_workers,
        running_tasks=running_tasks,
        workers=worker_names,
        resources_detail=resources_detail,
        pending_moderation=await _count(News.status == NewsStatus.PENDING),
        scheduled=await _count(News.status == NewsStatus.SCHEDULED),
        approved_waiting=await _count(News.status == NewsStatus.APPROVED),
        failed=await _count(News.status == NewsStatus.FAILED),
        published_today=await _count(
            News.status == NewsStatus.PUBLISHED, News.published_at >= midnight
        ),
    )
