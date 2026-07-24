"""News item model + version history for rollback."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB, FloatArray, StringArray
from shared.enums import NewsOrigin, NewsStatus

if TYPE_CHECKING:
    from shared.models.city import City
    from shared.models.media import MediaAsset


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
        default=NewsStatus.NEW,
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

    city: Mapped[City | None] = relationship(back_populates="news")
    media: Mapped[list[MediaAsset]] = relationship(
        back_populates="news", cascade="all, delete-orphan", order_by="MediaAsset.position"
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
