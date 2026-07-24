"""RSS/Atom feed parser."""

from __future__ import annotations

from datetime import datetime, timezone
from time import mktime

import feedparser

from shared.enums import MediaType, SourceType
from shared.exceptions import ParserError
from shared.logging import get_logger
from shared.plugins.parsers.base import (
    BaseParser,
    ParsedItem,
    ParsedMedia,
    parser_registry,
)
from shared.plugins.parsers.http import build_client

log = get_logger("parser.rss")


@parser_registry.register(SourceType.RSS.value)
class RSSParser(BaseParser):
    """Parse an RSS/Atom feed into :class:`ParsedItem` objects."""

    source_type = SourceType.RSS.value

    async def fetch(self) -> list[ParsedItem]:
        async with build_client(self.source) as client:
            try:
                response = await client.get(self.source.url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise ParserError(f"Failed to fetch RSS: {exc}") from exc

        feed = feedparser.parse(response.content)
        items: list[ParsedItem] = []

        for entry in feed.entries:
            text = (
                getattr(entry, "summary", None)
                or getattr(entry, "description", None)
                or (entry.content[0].value if getattr(entry, "content", None) else "")
                or ""
            ).strip()
            title = getattr(entry, "title", None)
            if not text and not title:
                continue

            published_at: datetime | None = None
            parsed_time = getattr(entry, "published_parsed", None) or getattr(
                entry, "updated_parsed", None
            )
            if parsed_time is not None:
                published_at = datetime.fromtimestamp(mktime(parsed_time), tz=timezone.utc)

            media: list[ParsedMedia] = []
            for enclosure in getattr(entry, "enclosures", []) or []:
                href = enclosure.get("href") or enclosure.get("url")
                mime = enclosure.get("type", "")
                if not href:
                    continue
                if mime.startswith("image"):
                    media.append(ParsedMedia(type=MediaType.PHOTO, url=href))
                elif mime.startswith("video"):
                    media.append(ParsedMedia(type=MediaType.VIDEO, url=href))
                elif mime.startswith("audio"):
                    media.append(ParsedMedia(type=MediaType.AUDIO, url=href))

            for media_content in getattr(entry, "media_content", []) or []:
                url = media_content.get("url")
                if url:
                    media.append(ParsedMedia(type=MediaType.PHOTO, url=url))

            items.append(
                ParsedItem(
                    title=title,
                    text=_strip_html(text),
                    url=getattr(entry, "link", None),
                    published_at=published_at,
                    guid=getattr(entry, "id", None) or getattr(entry, "link", None),
                    media=media,
                )
            )

        log.debug("rss_fetched", source=self.source.id, count=len(items))
        return items


def _strip_html(html: str) -> str:
    """Lightweight HTML → text (avoids heavy parsing for feed summaries)."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
