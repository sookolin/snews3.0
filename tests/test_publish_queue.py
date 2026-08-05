"""Tests for the publication queue spacing logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.enums import NewsStatus
from shared.models.news import News
from shared.models.setting import Setting

pytestmark = pytest.mark.asyncio


async def _set_interval(session, minutes: int) -> None:
    session.add(
        Setting(
            key="pipeline.publish_interval_minutes",
            value=minutes,
            category="pipeline",
        )
    )
    await session.flush()


def _news(**kwargs) -> News:  # type: ignore[no-untyped-def]
    # Spacing is now scoped per target channel/city; give every test item the
    # same city so these generic queue-mechanics tests still exercise shared
    # spacing (per-city isolation is covered separately).
    defaults = dict(original_text="text", original_title="t", city_id=1)
    defaults.update(kwargs)
    return News(**defaults)


async def test_first_item_publishes_immediately(db_session, monkeypatch) -> None:
    """With an empty queue the first approval goes out at once."""
    from workers import tasks

    sent: list[int] = []
    monkeypatch.setattr(tasks.publish_news, "delay", lambda nid, *a, **k: sent.append(nid))

    await _set_interval(db_session, 5)
    item = _news()
    db_session.add(item)
    await db_session.flush()

    slot = await tasks._schedule_publication(db_session, item)
    assert slot == "immediate"
    assert item.scheduled_at is None
    assert sent == [item.id]


async def test_second_item_is_spaced_after_recent_publication(db_session, monkeypatch) -> None:
    """A just-published post pushes the next one into a future slot."""
    from workers import tasks

    monkeypatch.setattr(tasks.publish_news, "delay", lambda nid, *a, **k: None)
    await _set_interval(db_session, 10)

    now = datetime.now(timezone.utc)
    published = _news(status=NewsStatus.PUBLISHED, published_at=now)
    db_session.add(published)
    await db_session.flush()

    nxt = _news()
    db_session.add(nxt)
    await db_session.flush()

    slot = await tasks._schedule_publication(db_session, nxt)
    assert slot != "immediate"
    assert nxt.status == NewsStatus.SCHEDULED
    assert nxt.scheduled_at is not None
    # Roughly 10 minutes ahead (allow a little execution drift).
    delta = nxt.scheduled_at - now
    assert timedelta(minutes=9) <= delta <= timedelta(minutes=11)


async def test_queue_stacks_multiple_approvals(db_session, monkeypatch) -> None:
    """Approving three items in a row yields three increasing slots."""
    from workers import tasks

    monkeypatch.setattr(tasks.publish_news, "delay", lambda nid, *a, **k: None)
    await _set_interval(db_session, 5)

    now = datetime.now(timezone.utc)
    db_session.add(_news(status=NewsStatus.PUBLISHED, published_at=now))
    await db_session.flush()

    slots = []
    for _ in range(3):
        item = _news()
        db_session.add(item)
        await db_session.flush()
        await tasks._schedule_publication(db_session, item)
        slots.append(item.scheduled_at)

    assert all(s is not None for s in slots)
    assert slots[0] < slots[1] < slots[2]


async def test_immediate_flag_skips_the_queue(db_session, monkeypatch) -> None:
    """publish_immediately bypasses spacing even with a busy queue."""
    from workers import tasks

    sent: list[int] = []
    monkeypatch.setattr(tasks.publish_news, "delay", lambda nid, *a, **k: sent.append(nid))
    await _set_interval(db_session, 30)

    now = datetime.now(timezone.utc)
    db_session.add(_news(status=NewsStatus.PUBLISHED, published_at=now))
    await db_session.flush()

    urgent = _news(publish_immediately=True)
    db_session.add(urgent)
    await db_session.flush()

    slot = await tasks._schedule_publication(db_session, urgent)
    assert slot == "immediate"
    assert urgent.scheduled_at is None
    assert sent == [urgent.id]
