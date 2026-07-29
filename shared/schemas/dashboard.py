"""Dashboard / monitoring schemas."""

from __future__ import annotations

from pydantic import BaseModel


class StatusCount(BaseModel):
    status: str
    count: int


class TimeSeriesPoint(BaseModel):
    date: str
    count: int


class SourceStat(BaseModel):
    """Throughput of a single source — what it brought and what got published."""

    name: str
    total: int
    published: int


class HourPoint(BaseModel):
    hour: int
    count: int


class DashboardStats(BaseModel):
    total_news: int
    published: int
    pending: int
    rejected: int
    failed: int
    duplicates: int
    total_cities: int
    active_sources: int
    total_sources: int
    total_channels: int
    active_channels: int
    #: Top sources by volume over the last 30 days, with their publish rate.
    top_sources: list[SourceStat] = []
    #: Publications per hour of day (last 30 days) — shows when the feed is busy.
    by_hour: list[HourPoint] = []
    #: Average minutes between ingest and publication over the last 30 days.
    avg_moderation_minutes: float = 0.0
    bot_submissions: int = 0
    bot_unique_users: int = 0
    bot_anonymous: int = 0
    by_status: list[StatusCount]
    last_7_days: list[TimeSeriesPoint]


class ServiceHealth(BaseModel):
    name: str
    healthy: bool
    detail: str | None = None


class SystemStatus(BaseModel):
    services: list[ServiceHealth]
    cpu_percent: float
    memory_percent: float
    queue_depth: int
    active_workers: int
    #: Tasks a worker has picked up / reserved right now.
    running_tasks: int = 0
    #: Pipeline counters straight from the database — these stay meaningful even
    #: when Redis or Celery are unreachable.
    pending_moderation: int = 0
    scheduled: int = 0
    approved_waiting: int = 0
    failed: int = 0
    published_today: int = 0
    #: Worker names, so it is obvious which node answered the ping.
    workers: list[str] = []
    #: Set when host metrics are unavailable (e.g. psutil not installed).
    resources_detail: str | None = None
