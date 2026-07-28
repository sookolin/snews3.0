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

            media = _extract_media(entry, text)

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


_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
_VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")


def _kind_for(url: str, mime: str = "") -> MediaType | None:
    """Classify a media URL by MIME type, then by file extension."""
    mime = (mime or "").lower()
    if mime.startswith("image"):
        return MediaType.ANIMATION if mime.endswith("gif") else MediaType.PHOTO
    if mime.startswith("video"):
        return MediaType.VIDEO
    if mime.startswith("audio"):
        return MediaType.AUDIO

    lowered = url.lower().split("?")[0]
    if lowered.endswith(".gif"):
        return MediaType.ANIMATION
    if lowered.endswith(_IMAGE_EXT):
        return MediaType.PHOTO
    if lowered.endswith(_VIDEO_EXT):
        return MediaType.VIDEO
    return None


def _extract_media(entry: object, description_html: str) -> list[ParsedMedia]:
    """Collect media from every common RSS/Atom convention.

    Feeds advertise images in wildly different ways, so we check, in order:
    ``enclosures``, ``media_content``, ``media_thumbnail``, ``links`` with an
    image MIME, and finally ``<img>`` tags inside the description HTML.
    """
    media: list[ParsedMedia] = []
    seen: set[str] = set()

    def add(url: str | None, mime: str = "", *, assume_image: bool = False) -> None:
        if not url or url in seen:
            return
        if not url.startswith(("http://", "https://")):
            return
        kind = _kind_for(url, mime)
        if kind is None and assume_image:
            kind = MediaType.PHOTO
        if kind is None:
            return
        seen.add(url)
        media.append(ParsedMedia(type=kind, url=url))

    for enclosure in getattr(entry, "enclosures", None) or []:
        add(enclosure.get("href") or enclosure.get("url"), enclosure.get("type", ""))

    # <media:content> — usually carries an explicit medium/type.
    for content in getattr(entry, "media_content", None) or []:
        add(content.get("url"), content.get("type", ""), assume_image=True)

    # <media:thumbnail> — always an image, often without a MIME type.
    for thumb in getattr(entry, "media_thumbnail", None) or []:
        add(thumb.get("url"), assume_image=True)

    # Atom <link rel="enclosure" type="image/...">.
    for link in getattr(entry, "links", None) or []:
        if link.get("rel") == "enclosure":
            add(link.get("href"), link.get("type", ""))

    # Fall back to images embedded in the description/content HTML.
    if not media and description_html:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(description_html, "lxml")
            for img in soup.find_all("img"):
                add(img.get("src") or img.get("data-src"), assume_image=True)
        except Exception:  # noqa: BLE001 - media is best-effort
            pass

    return media
