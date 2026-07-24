"""Base publisher interface."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from shared.models.channel import Channel
from shared.models.media import MediaAsset
from shared.plugins.registry import Registry


@dataclass
class PublishRequest:
    """Everything a publisher needs to deliver one news item."""

    text: str
    media: list[MediaAsset] = field(default_factory=list)
    disable_web_preview: bool = True
    is_spoiler: bool = False


@dataclass
class PublishResult:
    """Result of a publish attempt."""

    success: bool
    message_ids: list[int] = field(default_factory=list)
    error: str | None = None


class BasePublisher(abc.ABC):
    """Abstract publisher targeting a single channel."""

    publisher_type: str = ""

    def __init__(self, channel: Channel) -> None:
        self.channel = channel

    @abc.abstractmethod
    async def publish(self, request: PublishRequest) -> PublishResult:
        """Publish ``request`` to :attr:`channel`."""
        raise NotImplementedError


publisher_registry: Registry[type[BasePublisher]] = Registry("publisher")
