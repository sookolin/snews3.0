"""Runtime settings model — key/value store editable from the web panel."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB


class Setting(Base, TimestampMixin):
    """A single configurable parameter stored as JSON.

    All *business* parameters (feature toggles, notification config, i18n
    overrides, default profile ids, etc.) live here so they can be changed from
    the web panel without code changes or redeploys.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Setting {self.key}={self.value!r}>"
