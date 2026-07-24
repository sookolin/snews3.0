"""Generic JSON API parser.

Maps a JSON response to items using ``source.selectors`` with dotted paths::

    {
      "root": "data.articles",   # path to the list (empty = response is a list)
      "title": "title",
      "text": "body",
      "url": "url",
      "image": "image_url",
      "guid": "id"
    }
"""

from __future__ import annotations

from typing import Any

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

log = get_logger("parser.api")


def _dig(obj: Any, path: str | None) -> Any:
    """Traverse a dotted path in nested dict/list structures."""
    if not path:
        return obj
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


@parser_registry.register(SourceType.API.value)
class APIParser(BaseParser):
    """Parse a JSON API endpoint into items."""

    source_type = SourceType.API.value

    async def fetch(self) -> list[ParsedItem]:
        async with build_client(self.source) as client:
            try:
                response = await client.get(self.source.url)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise ParserError(f"Failed to fetch API: {exc}") from exc

        selectors = self.source.selectors or {}
        root = _dig(payload, selectors.get("root")) if selectors.get("root") else payload
        if isinstance(root, dict):
            root = [root]
        if not isinstance(root, list):
            raise ParserError("API root did not resolve to a list of items")

        items: list[ParsedItem] = []
        for entry in root:
            title = _dig(entry, selectors.get("title", "title"))
            text = _dig(entry, selectors.get("text", "text")) or _dig(entry, "description")
            if not text and not title:
                continue
            url = _dig(entry, selectors.get("url", "url"))
            image = _dig(entry, selectors.get("image", "image"))
            guid = _dig(entry, selectors.get("guid", "id")) or url

            media = (
                [ParsedMedia(type=MediaType.PHOTO, url=str(image))]
                if isinstance(image, str) and image
                else []
            )
            items.append(
                ParsedItem(
                    title=str(title) if title else None,
                    text=str(text or title),
                    url=str(url) if url else None,
                    guid=str(guid) if guid else None,
                    media=media,
                )
            )

        log.debug("api_fetched", source=self.source.id, count=len(items))
        return items
