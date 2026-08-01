"""City schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from shared.schemas.common import ORMModel


class CityBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    extra_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    region: str | None = None
    country: str | None = None
    language: str = "ru"
    is_active: bool = True
    template_id: int | None = None
    kind: Literal["city", "other"] = "city"
    is_world_bucket: bool = False
    # Daily weather post configuration.
    weather_enabled: bool = False
    weather_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weather_lat: float | None = None
    weather_lon: float | None = None


class CityCreate(CityBase):
    pass


class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    keywords: list[str] | None = None
    extra_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    region: str | None = None
    country: str | None = None
    language: str | None = None
    is_active: bool | None = None
    template_id: int | None = None
    telegram_topic_id: int | None = None
    kind: Literal["city", "other"] | None = None
    is_world_bucket: bool | None = None
    weather_enabled: bool | None = None
    weather_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weather_lat: float | None = None
    weather_lon: float | None = None


class CityOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None
    keywords: list[str]
    extra_keywords: list[str]
    exclude_keywords: list[str]
    region: str | None
    country: str | None
    language: str
    is_active: bool
    telegram_topic_id: int | None
    template_id: int | None
    kind: str = "city"
    is_world_bucket: bool = False
    weather_enabled: bool = False
    weather_time: str | None = None
    weather_lat: float | None = None
    weather_lon: float | None = None
    created_at: datetime
