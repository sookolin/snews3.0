"""Telegram public channel parser.

Reads a public channel's web preview (``https://t.me/s/<channel>``) which does
not require the Bot API and works for any public channel. The source URL may be
a channel username, ``t.me/<name>`` or the full preview URL.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

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

log = get_logger("parser.telegram")

_BG_IMAGE_RE = re.compile(r"background-image:\s*url\(['\"]?(?P<url>[^'\")]+)")


def _normalise_channel_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("@"):
        return f"https://t.me/s/{raw[1:]}"
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    path = parsed.path.strip("/")
    if path.startswith("s/"):
        return f"https://t.me/{path}"
    return f"https://t.me/s/{path}"


@parser_registry.register(SourceType.TELEGRAM.value)
class TelegramParser(BaseParser):
    """Parse a public Telegram channel via its web preview page."""

    source_type = SourceType.TELEGRAM.value

    async def fetch(self) -> list[ParsedItem]:
        from bs4 import BeautifulSoup

        url = _normalise_channel_url(self.source.url)
        async with build_client(self.source) as client:
            try:
                # t.me/s/ serves the full message list only to browser-like
                # clients. With the generic bot UA Telegram returns a stripped
                # page (no ``.tgme_widget_message_wrap``), so channels appeared
                # to "not parse". Send realistic browser headers and request the
                # embedded view explicitly.
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/125.0.0.0 Safari/537.36"
                        ),
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;"
                            "q=0.9,image/avif,image/webp,*/*;q=0.8"
                        ),
                        "Accept-Language": "ru,en;q=0.9",
                    },
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise ParserError(f"Failed to fetch Telegram channel: {exc}") from exc

        soup = BeautifulSoup(response.text, "lxml")
        items: list[ParsedItem] = []

        for wrap in soup.select(".tgme_widget_message_wrap"):
            text_node = wrap.select_one(".tgme_widget_message_text")
            text = text_node.get_text("\n", strip=True) if text_node else ""

            link_node = wrap.select_one("a.tgme_widget_message_date")
            post_url = link_node.get("href") if link_node else None

            # Collect media first so photo/video-only posts (no text caption)
            # are not silently dropped — many channels post images with an empty
            # or very short caption, and skipping them lost real news.
            media: list[ParsedMedia] = []
            for photo in wrap.select(".tgme_widget_message_photo_wrap"):
                style = photo.get("style", "")
                match = _BG_IMAGE_RE.search(style)
                if match:
                    media.append(ParsedMedia(type=MediaType.PHOTO, url=match.group("url")))
            for video in wrap.select("video"):
                src = video.get("src")
                if src:
                    media.append(ParsedMedia(type=MediaType.VIDEO, url=src))

            # Skip only truly empty posts (no text AND no media): service
            # messages, join notices, poll stubs, etc.
            if not text and not media:
                continue

            # Parse the post timestamp from the <time datetime="..."> element
            # inside the message date link so we can populate source_published_at.
            published_at: datetime | None = None
            time_node = wrap.select_one("a.tgme_widget_message_date time[datetime]")
            if time_node:
                raw_dt = time_node.get("datetime", "")
                try:
                    published_at = datetime.fromisoformat(
                        raw_dt.replace("Z", "+00:00") if isinstance(raw_dt, str) else ""
                    )
                except (ValueError, TypeError):
                    pass

            # For media-only posts use a minimal placeholder so downstream
            # dedup/AI still have something to work with.
            body = text or "📷 Медиа-публикация"
            first_line = body.split("\n", 1)[0][:200]
            items.append(
                ParsedItem(
                    title=first_line,
                    text=body,
                    url=post_url,
                    guid=post_url,
                    media=media,
                    published_at=published_at,
                )
            )

        log.debug("telegram_fetched", source=self.source.id, count=len(items))
        return items
