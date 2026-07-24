"""News source model + source↔city association table."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB
from shared.enums import ParserEngine, SourceType

if TYPE_CHECKING:
    from shared.models.city import City

# Many-to-many: a source can feed several cities.
source_cities = Table(
    "source_cities",
    Base.metadata,
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    Column("city_id", ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
)


class Source(Base, TimestampMixin):
    """A news source polled by the workers."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, native_enum=False, length=32), nullable=False
    )
    parser_engine: Mapped[ParserEngine] = mapped_column(
        Enum(ParserEngine, native_enum=False, length=32),
        default=ParserEngine.AUTO,
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    check_interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Fetch behaviour
    use_proxy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(String(2048))
    headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    cookies: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    auth: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # CSS/XPath selectors for HTML/website parsers
    selectors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Runtime state
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    cities: Mapped[list[City]] = relationship(secondary=source_cities, lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source {self.id} {self.name} {self.type}>"
