"""Advertisement model — paid promotional posts with delivery stats."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB
from shared.enums import AdStatus


class Ad(Base, TimestampMixin):
    """A paid advertisement that can be published to channels like a news post."""

    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Internal name (admin list only, never published).
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Published heading (goes into the post / template {title}).
    heading: Mapped[str | None] = mapped_column(String(512))
    advertiser: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[AdStatus] = mapped_column(
        Enum(AdStatus, native_enum=False, length=16),
        default=AdStatus.DRAFT,
        nullable=False,
        index=True,
    )

    # Target channel (optional; if null, admin picks at publish time)
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL")
    )
    # Publication template override (optional).
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL")
    )

    # Inline keyboard buttons (list of rows of {text, url})
    buttons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Media URLs to attach
    media_urls: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Uploaded media: list of {path, type} stored under MEDIA_ROOT.
    media_files: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Geolocation attached to the ad post.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_title: Mapped[str | None] = mapped_column(String(255))
    location_address: Mapped[str | None] = mapped_column(String(512))

    # Recurring auto-publication schedule:
    #   {"times": ["09:00","18:00"], "weekdays": [1,3,5],
    #    "day_parity": "even"|"odd"|"any", "date_from": "...", "date_to": "..."}
    schedule: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Commercial / legal (Russian ad marking law) / stats
    price: Mapped[float | None] = mapped_column(Float)
    erid: Mapped[str | None] = mapped_column(String(128))
    advertiser_inn: Mapped[str | None] = mapped_column(String(32))
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_message_ids: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ad {self.id} {self.title} {self.status}>"
