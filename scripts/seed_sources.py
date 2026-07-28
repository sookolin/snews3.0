"""Seed a set of popular Russian news sources.

Adds well-known RSS feeds (federal + Krasnodar region) so the admin panel has
working sources out of the box. Idempotent: sources are matched by URL.

Usage::

    python -m scripts.seed_sources                # federal + all regional
    python -m scripts.seed_sources --city 5       # bind regional feeds to city 5
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

#: Federal feeds — matched to cities by keywords (no explicit city binding).
FEDERAL: list[dict] = [
    {"name": "Lenta.ru", "url": "https://lenta.ru/rss/news", "interval": 300},
    {"name": "RIA Новости", "url": "https://ria.ru/export/rss2/archive/index.xml", "interval": 300},
    {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp", "interval": 300},
    {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml", "interval": 300},
    {"name": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/news.xml", "interval": 300},
    {"name": "РБК", "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "interval": 300},
    {"name": "Газета.Ru", "url": "https://www.gazeta.ru/export/rss/lenta.xml", "interval": 300},
    {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml", "interval": 300},
    {"name": "Российская газета", "url": "https://rg.ru/xml/index.xml", "interval": 300},
    {"name": "Ведомости", "url": "https://www.vedomosti.ru/rss/news", "interval": 300},
]

#: Krasnodar-region feeds — bound to the city when --city is given.
KRASNODAR: list[dict] = [
    {"name": "Юга.ру", "url": "https://www.yuga.ru/rss/", "interval": 240},
    {"name": "Кубанские новости", "url": "https://kubnews.ru/rss/", "interval": 240},
    {"name": "Живая Кубань", "url": "https://livekuban.ru/rss.xml", "interval": 240},
    {"name": "Краснодарские известия", "url": "https://ki-news.ru/feed/", "interval": 240},
    {
        "name": "Блокнот Краснодар",
        "url": "https://bloknot-krasnodar.ru/rss_yandex.php",
        "interval": 240,
    },
    {"name": "93.ru Краснодар", "url": "https://93.ru/text/rss.xml", "interval": 240},
]


async def _upsert(session, spec: dict, city_ids: list[int]) -> bool:  # type: ignore[no-untyped-def]
    """Create the source if its URL is new; returns True when created."""
    existing = await session.scalar(select(Source).where(Source.url == spec["url"]))
    if existing is not None:
        return False

    source = Source(
        name=spec["name"],
        url=spec["url"],
        type=SourceType.RSS,
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


async def seed_sources(city_id: int | None = None) -> None:
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

        created = 0
        for spec in FEDERAL:
            if await _upsert(session, spec, []):
                created += 1
        for spec in KRASNODAR:
            if await _upsert(session, spec, regional_cities):
                created += 1

        await session.commit()
        log.info("seed_sources_done", created=created)
        print(f"Создано источников: {created}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed popular news sources")
    parser.add_argument(
        "--city", type=int, default=None,
        help="City id to bind regional (Krasnodar) feeds to",
    )
    args = parser.parse_args()
    asyncio.run(seed_sources(args.city))


if __name__ == "__main__":
    main()
