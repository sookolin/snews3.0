"""News item model + version history for rollback."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB, FloatArray, StringArray
from shared.enums import NewsOrigin, NewsStatus

if TYPE_CHECKING:
    from shared.models.city import City
    from shared.models.media import MediaAsset


# Many-to-many: a single news item can target several cities at once (e.g. a
# regional agency covering the whole oblast). This replaces cloning the item
# into one News row per city — instead there is ONE News shown with multiple
# channels, published to all of them with a single action.
news_target_cities = Table(
    "news_target_cities",
    Base.metadata,
    Column("news_id", ForeignKey("news.id", ondelete="CASCADE"), primary_key=True),
    Column("city_id", ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
)


class News(Base, TimestampMixin):
    """A discovered / submitted news item flowing through the pipeline."""

    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Original (raw) content
    original_title: Mapped[str | None] = mapped_column(String(1024))
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[str | None] = mapped_column(String(2048))

    # AI-processed content (what gets published)
    title: Mapped[str | None] = mapped_column(String(1024))
    text: Mapped[str | None] = mapped_column(Text)

    status: Mapped[NewsStatus] = mapped_column(
        Enum(NewsStatus, native_enum=False, length=32),
        default=NewsStatus.PROCESSING,
        nullable=False,
        index=True,
    )
    origin: Mapped[NewsOrigin] = mapped_column(
        Enum(NewsOrigin, native_enum=False, length=16),
        default=NewsOrigin.PARSER,
        nullable=False,
    )

    # Relations
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id", ondelete="SET NULL"))
    ai_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_profiles.id", ondelete="SET NULL")
    )

    # Dedup fingerprints
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    simhash: Mapped[int | None] = mapped_column(BigInteger)
    embedding: Mapped[list[float] | None] = mapped_column(FloatArray)
    match_score: Mapped[float | None] = mapped_column(Float)
    matched_keywords: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)

    # Publication flags/settings
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    apply_watermark: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Geolocation (attached to the post as a Telegram location/venue)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_title: Mapped[str | None] = mapped_column(String(255))
    location_address: Mapped[str | None] = mapped_column(String(512))

    # Inline keyboard buttons: list of rows, each row a list of {text, url}.
    buttons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Emoji chosen (by AI or editor) to accent the title.
    emoji: Mapped[str | None] = mapped_column(String(16))

    # Manual source override (used instead of the linked Source name) and a
    # flag to hide the source line entirely for this post.
    source_name: Mapped[str | None] = mapped_column(String(255))
    hide_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Manual link to the original publication (used for the {source} hyperlink
    # when it differs from ``original_url``).
    source_url_override: Mapped[str | None] = mapped_column(String(2048))

    # When the item was published at the original source (moderator info only).
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When a moderator approved/processed the item (moderator info only).
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the AI rewrite finished (internal diagnostics).
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Skip the publication queue and go out immediately.
    publish_immediately: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Edited after being published (shown as an extra "изменено" tag).
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Follow-up threading: publish as a reply to this earlier news' message.
    reply_to_news_id: Mapped[int | None] = mapped_column(
        ForeignKey("news.id", ondelete="SET NULL")
    )
    # Marked as world news: allowed through even without a city keyword match.
    is_world_news: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # User submission metadata
    submitted_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    submitted_anonymously: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255))

    # Moderation
    moderated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    moderation_message_id: Mapped[int | None] = mapped_column(BigInteger)

    # Publication result (message ids per channel)
    published_message_ids: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    #: City ids that have already been approved for this (possibly multi-city)
    #: item. Used to support partial approval: a moderator whose access is
    #: restricted to some cities only approves/publishes to those; the item
    #: stays pending for the remaining target cities until someone with
    #: access to them (or a super admin) approves it too.
    approved_city_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)

    city: Mapped[City | None] = relationship(back_populates="news")
    #: All cities this item should be published to. When empty, the item targets
    #: only ``city_id`` (backwards compatible). The primary ``city_id`` stays the
    #: moderation-topic owner and the first target.
    target_cities: Mapped[list[City]] = relationship(
        secondary=news_target_cities, lazy="selectin"
    )
    media: Mapped[list[MediaAsset]] = relationship(
        back_populates="news",
        cascade="all, delete-orphan",
        order_by="MediaAsset.position",
        lazy="selectin",
    )
    versions: Mapped[list[NewsVersion]] = relationship(
        back_populates="news",
        cascade="all, delete-orphan",
        order_by="NewsVersion.version.desc()",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<News {self.id} {self.status} city={self.city_id}>"


class NewsVersion(Base, TimestampMixin):
    """Immutable snapshot of a news item for history & rollback."""

    __tablename__ = "news_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str | None] = mapped_column(String(1024))
    text: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comment: Mapped[str | None] = mapped_column(String(512))

    news: Mapped[News] = relationship(back_populates="versions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NewsVersion news={self.news_id} v{self.version}>"
