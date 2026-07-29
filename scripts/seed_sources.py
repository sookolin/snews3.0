"""Seed the working set of Krasnodar news sources.

Adds the RSS feeds plus the test Telegram channel so the admin panel has
working sources out of the box. Idempotent: sources are matched by URL.

Usage::

    python -m scripts.seed_sources                # add the seed list
    python -m scripts.seed_sources --city 5       # bind feeds to city 5
    python -m scripts.seed_sources --replace      # drop everything not listed here
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from shared.database import session_scope
from shared.enums import ParserEngine, SourceType
from shared.logging import configure_logging, get_logger
from shared.models.city import City
from shared.models.source import Source, source_cities

log = get_logger("seed_sources")

#: No federal feeds are seeded any more — the list below is the whole set.
FEDERAL: list[dict] = []

#: Krasnodar-region feeds — bound to the city when --city is given.
KRASNODAR: list[dict] = [
    {"name": "93.ru Краснодар", "url": "https://93.ru/text/rss.xml", "interval": 240},
    {"name": "РБК Краснодар", "url": "https://kuban.rbc.ru/kuban/rss/", "interval": 240},
    {
        "name": "Блокнот Краснодар",
        "url": "https://bloknot-krasnodar.ru/rss_yandex.php",
        "interval": 240,
    },
    {"name": "КП Кубань", "url": "https://www.kuban.kp.ru/rss/allsections.xml", "interval": 240},
    {"name": "КраснодарМедиа", "url": "https://krasnodarmedia.su/rss/", "interval": 240},
    {"name": "Югополис", "url": "https://www.yugopolis.ru/rss/", "interval": 240},
]

#: Telegram channels parsed through the telegram parser plugin.
TELEGRAM: list[dict] = [
    {
        "name": "SNews тест",
        "url": "https://t.me/snewstest123",
        "interval": 180,
        "type": SourceType.TELEGRAM,
    },
]


async def _upsert(session, spec: dict, city_ids: list[int]) -> bool:  # type: ignore[no-untyped-def]
    """Create the source if its URL is new; returns True when created."""
    existing = await session.scalar(select(Source).where(Source.url == spec["url"]))
    if existing is not None:
        return False

    source = Source(
        name=spec["name"],
        url=spec["url"],
        type=spec.get("type", SourceType.RSS),
        parser_engine=ParserEngine.AUTO,
        check_interval_seconds=spec.get("interval", 300),
        timeout_seconds=30,
        priority=spec.get("priority", 100),
        is_active=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        },
    )
    session.add(source)
    await session.flush()

    if city_ids:
        from sqlalchemy import insert

        await session.execute(
            insert(source_cities),
            [{"source_id": source.id, "city_id": cid} for cid in city_ids],
        )
    return True


async def seed_sources(city_id: int | None = None, replace: bool = False) -> None:
    configure_logging()
    async with session_scope() as session:
        # Resolve the target city for regional feeds.
        regional_cities: list[int] = []
        if city_id is not None:
            city = await session.get(City, city_id)
            if city is None:
                log.error("city_not_found", city=city_id)
            else:
                regional_cities = [city.id]
                log.info("binding_regional_feeds", city=city.name)

        removed = 0
        if replace:
            keep = {s["url"] for s in FEDERAL + KRASNODAR + TELEGRAM}
            stale = (await session.scalars(select(Source).where(Source.url.not_in(keep)))).all()
            for source in stale:
                await session.delete(source)
                removed += 1
            await session.flush()
            log.info("stale_sources_removed", count=removed)

        created = 0
        for spec in FEDERAL:
            if await _upsert(session, spec, []):
                created += 1
        for spec in KRASNODAR + TELEGRAM:
            if await _upsert(session, spec, regional_cities):
                created += 1

        await session.commit()
        log.info("seed_sources_done", created=created, removed=removed)
        print(f"Создано источников: {created}, удалено прежних: {removed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed popular news sources")
    parser.add_argument(
        "--city", type=int, default=None,
        help="City id to bind regional (Krasnodar) feeds to",
    )
    parser.add_argument(
        "--replace", action="store_true",
        help="Delete every source that is not in this seed list",
    )
    args = parser.parse_args()
    asyncio.run(seed_sources(args.city, args.replace))


if __name__ == "__main__":
    main()
