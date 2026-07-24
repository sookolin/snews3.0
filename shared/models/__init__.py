"""SQLAlchemy ORM models package.

Importing this package registers every model with the declarative ``Base``
metadata, which is required for Alembic autogeneration and ``create_all``.
"""

from __future__ import annotations

from shared.models.ai import AIProfile
from shared.models.audit import AuditLog
from shared.models.channel import Channel
from shared.models.city import City
from shared.models.media import MediaAsset
from shared.models.news import News, NewsVersion
from shared.models.setting import Setting
from shared.models.source import Source, source_cities
from shared.models.template import Template
from shared.models.user import User
from shared.models.watermark import WatermarkProfile

__all__ = [
    "AIProfile",
    "AuditLog",
    "Channel",
    "City",
    "MediaAsset",
    "News",
    "NewsVersion",
    "Setting",
    "Source",
    "source_cities",
    "Template",
    "User",
    "WatermarkProfile",
]
