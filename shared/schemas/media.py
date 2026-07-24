"""Media schemas."""

from __future__ import annotations

from shared.enums import MediaType
from shared.schemas.common import ORMModel


class MediaOut(ORMModel):
    id: int
    news_id: int
    type: MediaType
    file_path: str | None
    processed_path: str | None
    remote_url: str | None
    telegram_file_id: str | None
    mime_type: str | None
    file_size: int | None
    width: int | None
    height: int | None
    duration: int | None
    caption: str | None
    position: int
    is_spoiler: bool
    is_enabled: bool


class MediaUpdate(ORMModel):
    caption: str | None = None
    position: int | None = None
    is_spoiler: bool | None = None
    is_enabled: bool | None = None
