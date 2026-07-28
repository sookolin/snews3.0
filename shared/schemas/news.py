"""News schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import NewsOrigin, NewsStatus
from shared.schemas.common import ORMModel
from shared.schemas.media import MediaOut


class NewsCreate(BaseModel):
    """Manual/user news creation."""

    original_title: str | None = None
    original_text: str = Field(min_length=1)
    original_url: str | None = None
    city_id: int | None = None
    source_id: int | None = None
    origin: NewsOrigin = NewsOrigin.USER
    submitted_by_telegram_id: int | None = None
    submitted_anonymously: bool = False
    author_name: str | None = None
    buttons: list = Field(default_factory=list)


class NewsUpdate(BaseModel):
    title: str | None = None
    text: str | None = None
    city_id: int | None = None
    template_id: int | None = None
    ai_profile_id: int | None = None
    is_spoiler: bool | None = None
    apply_watermark: bool | None = None
    scheduled_at: datetime | None = None
    status: NewsStatus | None = None
    rejection_reason: str | None = None
    edit_comment: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_title: str | None = None
    location_address: str | None = None
    buttons: list | None = None
    author_name: str | None = None
    submitted_anonymously: bool | None = None
    emoji: str | None = None
    source_id: int | None = None
    source_name: str | None = None
    hide_source: bool | None = None
    source_url_override: str | None = None
    publish_immediately: bool | None = None
    is_edited: bool | None = None
    is_world_news: bool | None = None


class NewsListItem(ORMModel):
    id: int
    title: str | None
    original_title: str | None
    status: NewsStatus
    origin: NewsOrigin
    city_id: int | None
    source_id: int | None
    match_score: float | None
    is_spoiler: bool
    author_name: str | None
    submitted_anonymously: bool
    moderated_by: int | None
    template_id: int | None
    emoji: str | None
    #: Set when the item came from the Telegram submission bot.
    submitted_by_telegram_id: int | None
    #: Extra state flags shown as additional tags next to the status.
    is_edited: bool
    is_world_news: bool
    #: Non-empty when the post is currently live in a channel.
    published_message_ids: dict
    #: Attachments, used for the hover preview in the news table.
    media: list[MediaOut]
    source_published_at: datetime | None
    processed_at: datetime | None
    scheduled_at: datetime | None
    published_at: datetime | None
    created_at: datetime


class NewsOut(ORMModel):
    id: int
    original_title: str | None
    original_text: str
    original_url: str | None
    title: str | None
    text: str | None
    status: NewsStatus
    origin: NewsOrigin
    city_id: int | None
    source_id: int | None
    template_id: int | None
    ai_profile_id: int | None
    content_hash: str | None
    match_score: float | None
    matched_keywords: list[str]
    is_spoiler: bool
    apply_watermark: bool
    scheduled_at: datetime | None
    published_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_title: str | None
    location_address: str | None
    buttons: list
    emoji: str | None
    source_name: str | None
    hide_source: bool
    source_url_override: str | None
    source_published_at: datetime | None
    processed_at: datetime | None
    ai_processed_at: datetime | None
    publish_immediately: bool
    is_edited: bool
    is_world_news: bool
    reply_to_news_id: int | None
    submitted_by_telegram_id: int | None
    submitted_anonymously: bool
    author_name: str | None
    moderated_by: int | None
    rejection_reason: str | None
    published_message_ids: dict
    error: str | None
    media: list[MediaOut]
    created_at: datetime
    updated_at: datetime


class NewsVersionOut(ORMModel):
    id: int
    news_id: int
    version: int
    title: str | None
    text: str | None
    snapshot: dict
    edited_by: int | None
    comment: str | None
    created_at: datetime
