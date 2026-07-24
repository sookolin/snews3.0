"""Source schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import ParserEngine, SourceType
from shared.schemas.common import ORMModel


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    type: SourceType
    parser_engine: ParserEngine = ParserEngine.AUTO
    priority: int = 100
    check_interval_seconds: int = Field(default=300, ge=30)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    is_active: bool = True
    use_proxy: bool = False
    proxy_url: str | None = None
    headers: dict = Field(default_factory=dict)
    cookies: dict = Field(default_factory=dict)
    auth: dict = Field(default_factory=dict)
    selectors: dict = Field(default_factory=dict)
    city_ids: list[int] = Field(default_factory=list)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    type: SourceType | None = None
    parser_engine: ParserEngine | None = None
    priority: int | None = None
    check_interval_seconds: int | None = Field(default=None, ge=30)
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    is_active: bool | None = None
    use_proxy: bool | None = None
    proxy_url: str | None = None
    headers: dict | None = None
    cookies: dict | None = None
    auth: dict | None = None
    selectors: dict | None = None
    city_ids: list[int] | None = None


class SourceOut(ORMModel):
    id: int
    name: str
    url: str
    type: SourceType
    parser_engine: ParserEngine
    priority: int
    check_interval_seconds: int
    timeout_seconds: int
    is_active: bool
    use_proxy: bool
    proxy_url: str | None
    headers: dict
    cookies: dict
    auth: dict
    selectors: dict
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    error_count: int
    created_at: datetime
