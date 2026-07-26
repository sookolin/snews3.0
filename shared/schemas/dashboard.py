"""Dashboard / monitoring schemas."""

from __future__ import annotations

from pydantic import BaseModel


class StatusCount(BaseModel):
    status: str
    count: int


class TimeSeriesPoint(BaseModel):
    date: str
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
    channels_by_city: list[dict] = []
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
