"""Advertisement schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import AdStatus
from shared.schemas.common import ORMModel


class AdBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    advertiser: str | None = None
    text: str = Field(min_length=1)
    channel_id: int | None = None
    buttons: list = Field(default_factory=list)
    media_urls: list = Field(default_factory=list)
    is_spoiler: bool = False
    scheduled_at: datetime | None = None
    price: float | None = None


class AdCreate(AdBase):
    pass


class AdUpdate(BaseModel):
    title: str | None = None
    advertiser: str | None = None
    text: str | None = None
    channel_id: int | None = None
    buttons: list | None = None
    media_urls: list | None = None
    is_spoiler: bool | None = None
    scheduled_at: datetime | None = None
    price: float | None = None
    status: AdStatus | None = None


class AdOut(ORMModel):
    id: int
    title: str
    advertiser: str | None
    text: str
    status: AdStatus
    channel_id: int | None
    buttons: list
    media_urls: list
    is_spoiler: bool
    scheduled_at: datetime | None
    published_at: datetime | None
    price: float | None
    impressions: int
    clicks: int
    published_message_ids: dict
    error: str | None
    created_at: datetime


class AdStats(BaseModel):
    total: int
    published: int
    draft: int
    scheduled: int
    total_impressions: int
    total_clicks: int
    total_revenue: float
    ctr: float
