"""Template schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import TemplateFormat
from shared.schemas.common import ORMModel


class TemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False
    is_active: bool = True
    format: TemplateFormat = TemplateFormat.TELEGRAM_HTML
    header: str = "🔥 <b>{title}</b>"
    body: str = "{text}"
    footer: str = 'Источник: {source}\n————————\n👉 <a href="{link}">Подписаться</a>'
    separator: str = "\n\n"
    custom_emoji_id: str | None = None
    subscribe_link: str | None = None
    variables: dict = Field(default_factory=dict)
    disable_web_preview: bool = True
    uppercase_title: bool = False


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    format: TemplateFormat | None = None
    header: str | None = None
    body: str | None = None
    footer: str | None = None
    separator: str | None = None
    custom_emoji_id: str | None = None
    subscribe_link: str | None = None
    variables: dict | None = None
    disable_web_preview: bool | None = None
    uppercase_title: bool | None = None


class TemplateOut(ORMModel):
    id: int
    name: str
    is_default: bool
    is_active: bool
    format: TemplateFormat
    header: str
    body: str
    footer: str
    separator: str
    custom_emoji_id: str | None
    subscribe_link: str | None
    variables: dict
    disable_web_preview: bool
    uppercase_title: bool
    created_at: datetime
