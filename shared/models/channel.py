"""Telegram channel model — a publication target bound to a city."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.enums import ChannelPublishMode

if TYPE_CHECKING:
    from shared.models.city import City


class Channel(Base, TimestampMixin):
    """A Telegram channel (or chat) to which a city's news are published."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Telegram chat id (e.g. -1001234567890) or @username
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Public @username (for preview link), and avatar image URL for preview
    username: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    # Optional topic id if the channel is a forum
    topic_id: Mapped[int | None] = mapped_column(Integer)

    publish_mode: Mapped[ChannelPublishMode] = mapped_column(
        Enum(ChannelPublishMode, native_enum=False, length=16),
        default=ChannelPublishMode.IMMEDIATE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Per-channel schedule window (minutes from midnight, optional)
    schedule_from_minute: Mapped[int | None] = mapped_column(Integer)
    schedule_to_minute: Mapped[int | None] = mapped_column(Integer)
    # Minimum delay between posts in seconds (rate limiting per channel)
    min_interval_seconds: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id", ondelete="SET NULL"))
    # Watermark profile applied to this channel's media. NULL = use the default
    # active profile (or none). Lets each channel brand its media differently.
    watermark_id: Mapped[int | None] = mapped_column(
        ForeignKey("watermark_profiles.id", ondelete="SET NULL")
    )

    city: Mapped[City] = relationship(back_populates="channels")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Channel {self.id} {self.title} {self.chat_id}>"
