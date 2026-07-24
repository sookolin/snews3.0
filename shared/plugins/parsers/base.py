"""Base parser interface and the parser registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import MediaType
from shared.models.source import Source
from shared.plugins.registry import Registry


@dataclass
class ParsedMedia:
    """A media attachment discovered by a parser."""

    type: MediaType
    url: str
    caption: str | None = None


@dataclass
class ParsedItem:
    """A single raw item returned by a parser (before dedup/matching/AI)."""

    title: str | None
    text: str
    url: str | None = None
    published_at: datetime | None = None
    media: list[ParsedMedia] = field(default_factory=list)
    # Stable external identifier for the item, if the source provides one.
    guid: str | None = None

    def identity(self) -> str:
        """Return the best available stable identity for dedup by URL/guid."""
        return self.guid or self.url or (self.title or "") + self.text[:64]


class BaseParser(abc.ABC):
    """Abstract parser. Implementations fetch and normalise source items."""

    #: SourceType value this parser handles (set by subclasses).
    source_type: str = ""

    def __init__(self, source: Source) -> None:
        self.source = source

    @abc.abstractmethod
    async def fetch(self) -> list[ParsedItem]:
        """Fetch and return the latest items from the source.

        Implementations must not raise for individual bad items; they should
        skip them. A raised exception indicates a source-level failure.
        """
        raise NotImplementedError


parser_registry: Registry[type[BaseParser]] = Registry("parser")
