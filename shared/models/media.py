"""Media asset model — attachments belonging to a news item."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.enums import MediaType

if TYPE_CHECKING:
    from shared.models.news import News


class MediaAsset(Base, TimestampMixin):
    """A single attachment (photo/video/document/…) for a news item."""

    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, native_enum=False, length=16), nullable=False
    )
    # Relative path under MEDIA_ROOT (original download)
    file_path: Mapped[str | None] = mapped_column(String(1024))
    # Path after watermarking / processing (what actually gets published)
    processed_path: Mapped[str | None] = mapped_column(String(1024))
    remote_url: Mapped[str | None] = mapped_column(String(2048))
    # Telegram file_id for re-use once uploaded
    telegram_file_id: Mapped[str | None] = mapped_column(String(512))

    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration: Mapped[int | None] = mapped_column(Integer)

    caption: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024))

    news: Mapped[News] = relationship(back_populates="media")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MediaAsset {self.id} {self.type} news={self.news_id}>"
