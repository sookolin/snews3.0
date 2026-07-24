"""Publisher plugins — deliver processed news to targets (Telegram, webhook…)."""

from __future__ import annotations

from shared.plugins.publishers import telegram_publisher as _tg  # noqa: F401,E402
from shared.plugins.publishers.base import (
    BasePublisher,
    PublishRequest,
    PublishResult,
    publisher_registry,
)

__all__ = [
    "BasePublisher",
    "PublishRequest",
    "PublishResult",
    "publisher_registry",
]
