"""Celery application factory and beat schedule.

Tasks bridge Celery's synchronous worker model to the async services by running
an event loop per task via :func:`run_async`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery import Celery
from celery.schedules import crontab

from shared.config import settings
from shared.logging import configure_logging

configure_logging()

celery_app = Celery(
    "citynews",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

# Periodic schedule (Celery Beat).
celery_app.conf.beat_schedule = {
    "dispatch-due-sources": {
        "task": "workers.tasks.dispatch_due_sources",
        "schedule": 60.0,  # check every minute which sources are due
    },
    "publish-scheduled-news": {
        "task": "workers.tasks.publish_scheduled_news",
        "schedule": 60.0,
    },
    "publish-scheduled-ads": {
        "task": "workers.tasks.publish_scheduled_ads",
        "schedule": 60.0,
    },
    "nightly-backup": {
        "task": "workers.tasks.run_backup",
        "schedule": crontab(hour=settings.backup_cron_hour, minute=0),
    },
    "cleanup-old-media": {
        "task": "workers.tasks.cleanup_temp_media",
        "schedule": crontab(hour=4, minute=30),
    },
    # Check once per hour which users have their daily digest scheduled for
    # the current hour and send the Telegram DM summary.
    "daily-bot-digest": {
        "task": "workers.tasks.send_daily_digests",
        "schedule": crontab(minute=5),
    },
    # Every minute, publish the daily weather post to any city whose configured
    # weather time matches the current minute (per the UI timezone offset).
    "publish-city-weather": {
        "task": "workers.tasks.publish_city_weather",
        "schedule": 60.0,
    },
}

_T = TypeVar("_T")


def run_async(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async coroutine to completion from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():  # pragma: no cover - defensive
            raise RuntimeError("event loop already running")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
