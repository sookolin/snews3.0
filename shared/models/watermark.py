"""Watermark profile model."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin


class WatermarkProfile(Base, TimestampMixin):
    """Configurable watermark applied to images and videos."""

    __tablename__ = "watermark_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Either a logo image or a text watermark (or both)
    logo_path: Mapped[str | None] = mapped_column(String(1024))
    text: Mapped[str | None] = mapped_column(String(255))

    # Position: one of top-left, top-right, bottom-left, bottom-right, center
    position: Mapped[str] = mapped_column(String(16), default="bottom-right", nullable=False)
    margin_x: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    margin_y: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    # Size as a fraction of the base image width (0..1) and opacity (0..1)
    scale: Mapped[float] = mapped_column(Float, default=0.18, nullable=False)
    opacity: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)

    # Text styling
    font_size: Mapped[int] = mapped_column(Integer, default=32, nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#FFFFFF", nullable=False)
    shadow: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shadow_color: Mapped[str] = mapped_column(String(16), default="#000000", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WatermarkProfile {self.id} {self.name}>"
