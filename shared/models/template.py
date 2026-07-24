"""Publication template model."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB
from shared.enums import TemplateFormat


class Template(Base, TimestampMixin):
    """A fully-editable publication template.

    The ``body`` supports placeholders rendered by
    :mod:`shared.services.template_renderer`:
    ``{title}``, ``{text}``, ``{source}``, ``{source_url}``, ``{city}``,
    ``{date}``, ``{link}``, ``{footer}`` and any custom ``variables``.
    """

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    format: Mapped[TemplateFormat] = mapped_column(
        Enum(TemplateFormat, native_enum=False, length=32),
        default=TemplateFormat.TELEGRAM_HTML,
        nullable=False,
    )

    # Structural pieces (all editable)
    header: Mapped[str] = mapped_column(Text, default="🔥 <b>{title}</b>", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="{text}", nullable=False)
    footer: Mapped[str] = mapped_column(
        Text,
        default='Источник: {source}\n————————\n👉 <a href="{link}">Подписаться</a>',
        nullable=False,
    )
    separator: Mapped[str] = mapped_column(String(64), default="\n\n", nullable=False)

    # Custom emoji / subscribe link / extra variables
    custom_emoji_id: Mapped[str | None] = mapped_column(String(64))
    subscribe_link: Mapped[str | None] = mapped_column(String(2048))
    variables: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Whether Telegram link previews are shown
    disable_web_preview: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Template {self.id} {self.name}>"
