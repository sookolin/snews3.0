"""City model. Each city maps to a Telegram topic in the moderation group."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.db_types import StringArray

if TYPE_CHECKING:
    from shared.models.channel import Channel
    from shared.models.news import News


class City(Base, TimestampMixin):
    """A monitored city with its matching keywords and Telegram topic."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Matching configuration
    keywords: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    extra_keywords: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    exclude_keywords: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)

    # Geography / locale
    region: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Telegram topic (thread) created automatically inside the moderation group
    telegram_topic_id: Mapped[int | None] = mapped_column(Integer)

    # Default template override for this city
    template_id: Mapped[int | None] = mapped_column(Integer)

    channels: Mapped[list[Channel]] = relationship(
        back_populates="city", cascade="all, delete-orphan"
    )
    news: Mapped[list[News]] = relationship(back_populates="city")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<City {self.id} {self.name}>"
