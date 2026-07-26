"""Dashboard statistics & system monitoring endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from backend.app.deps import DBSession, require_permission
from shared.enums import NewsOrigin, NewsStatus, Permission
from shared.models.channel import Channel
from shared.models.city import City
from shared.models.news import News
from shared.models.source import Source
from shared.models.user import User
from shared.schemas.dashboard import (
    DashboardStats,
    ServiceHealth,
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
    channels_by_city_rows = (
        await session.execute(
            select(City.name, func.count(Channel.id))
            .join(Channel, Channel.city_id == City.id, isouter=True)
            .group_by(City.id, City.name)
        )
    ).all()
    channels_by_city = [{"city": name, "count": count} for name, count in channels_by_city_rows]

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
        duplicates=await count_status(NewsStatus.DUPLICATE),
        total_cities=total_cities,
        active_sources=active_sources,
        total_sources=total_sources,
        total_channels=total_channels,
        active_channels=active_channels,
        channels_by_city=channels_by_city,
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

    # Redis + queue depth
    queue_depth = 0
    try:
        from shared.redis_client import get_redis

        redis = get_redis()
        await redis.ping()
        queue_depth = int(await redis.llen("celery") or 0)
        services.append(ServiceHealth(name="redis", healthy=True))
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceHealth(name="redis", healthy=False, detail=str(exc)))

    # Celery workers
    active_workers = 0
    try:
        from workers.celery_app import celery_app

        stats = celery_app.control.inspect(timeout=1).ping() or {}
        active_workers = len(stats)
        services.append(ServiceHealth(name="celery", healthy=active_workers > 0))
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceHealth(name="celery", healthy=False, detail=str(exc)))

    # Host resources (best-effort; psutil optional).
    cpu_percent = 0.0
    memory_percent = 0.0
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
    except Exception:  # noqa: BLE001
        pass

    return SystemStatus(
        services=services,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        queue_depth=queue_depth,
        active_workers=active_workers,
    )
