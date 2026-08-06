"""City model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String, Text
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

    #: ``city`` for a real city, ``other`` for non-geographic feeds such as
    #: «Мировые новости» or «Интернет». ``other`` entries never receive news
    #: matched to a city, and each of them becomes its own section in the panel.
    kind: Mapped[str] = mapped_column(String(16), default="city", nullable=False)

    #: Marks the entry that collects everything that matched no city (world /
    #: unmatched news). Only meaningful for ``kind == "other"``.
    is_world_bucket: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Default template override for this city
    template_id: Mapped[int | None] = mapped_column(Integer)

    # ── Daily weather post ───────────────────────────────────────────────────
    #: When on, a daily weather forecast is auto-published to this city's
    #: channels at ``weather_time`` (server-local HH:MM, 24h).
    weather_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Publication time as "HH:MM" (interpreted in the UI timezone offset).
    weather_time: Mapped[str | None] = mapped_column(String(5))
    #: Coordinates used to fetch the forecast. When empty the city ``name`` is
    #: geocoded once via Open-Meteo's free geocoding API.
    weather_lat: Mapped[float | None] = mapped_column(Float)
    weather_lon: Mapped[float | None] = mapped_column(Float)
    #: Local date (UI timezone) the weather post was last published for. Guards
    #: the "publish within a tolerance window" scheduler against posting twice
    #: the same day when several beat ticks fall inside the window.
    weather_last_published_on: Mapped[str | None] = mapped_column(String(10))

    channels: Mapped[list[Channel]] = relationship(
        back_populates="city", cascade="all, delete-orphan"
    )
    news: Mapped[list[News]] = relationship(back_populates="city")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<City {self.id} {self.name}>"
