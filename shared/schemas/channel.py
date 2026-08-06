"""Channel schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import ChannelPublishMode
from shared.schemas.common import ORMModel


class ChannelBase(BaseModel):
    city_id: int
    title: str = Field(min_length=1, max_length=255)
    chat_id: str = Field(min_length=1, max_length=64)
    username: str | None = None
    avatar_url: str | None = None
    publish_mode: ChannelPublishMode = ChannelPublishMode.IMMEDIATE
    is_active: bool = True
    schedule_from_minute: int | None = Field(default=None, ge=0, le=1439)
    schedule_to_minute: int | None = Field(default=None, ge=0, le=1439)
    min_interval_seconds: int = Field(default=0, ge=0)
    template_id: int | None = None
    watermark_id: int | None = None


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    title: str | None = None
    chat_id: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    publish_mode: ChannelPublishMode | None = None
    is_active: bool | None = None
    schedule_from_minute: int | None = Field(default=None, ge=0, le=1439)
    schedule_to_minute: int | None = Field(default=None, ge=0, le=1439)
    min_interval_seconds: int | None = Field(default=None, ge=0)
    template_id: int | None = None
    watermark_id: int | None = None


class ChannelOut(ORMModel):
    id: int
    city_id: int
    title: str
    chat_id: str
    username: str | None
    avatar_url: str | None
    publish_mode: ChannelPublishMode
    is_active: bool
    schedule_from_minute: int | None
    schedule_to_minute: int | None
    min_interval_seconds: int
    template_id: int | None
    watermark_id: int | None
    created_at: datetime
