"""Pydantic v2 schemas (request/response DTOs)."""

from __future__ import annotations

from shared.schemas.ai import AIProfileCreate, AIProfileOut, AIProfileUpdate
from shared.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    TwoFactorSetup,
    TwoFactorVerify,
)
from shared.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from shared.schemas.city import CityCreate, CityOut, CityUpdate
from shared.schemas.common import Page, PaginationParams
from shared.schemas.dashboard import DashboardStats
from shared.schemas.media import MediaOut, MediaUpdate
from shared.schemas.news import (
    NewsCreate,
    NewsListItem,
    NewsOut,
    NewsUpdate,
    NewsVersionOut,
)
from shared.schemas.setting import SettingOut, SettingUpdate
from shared.schemas.source import SourceCreate, SourceOut, SourceUpdate
from shared.schemas.template import TemplateCreate, TemplateOut, TemplateUpdate
from shared.schemas.user import UserCreate, UserOut, UserUpdate
from shared.schemas.watermark import (
    WatermarkCreate,
    WatermarkOut,
    WatermarkUpdate,
)

__all__ = [
    "AIProfileCreate",
    "AIProfileOut",
    "AIProfileUpdate",
    "ChannelCreate",
    "ChannelOut",
    "ChannelUpdate",
    "CityCreate",
    "CityOut",
    "CityUpdate",
    "DashboardStats",
    "LoginRequest",
    "MediaOut",
    "MediaUpdate",
    "NewsCreate",
    "NewsListItem",
    "NewsOut",
    "NewsUpdate",
    "NewsVersionOut",
    "Page",
    "PaginationParams",
    "RefreshRequest",
    "SettingOut",
    "SettingUpdate",
    "SourceCreate",
    "SourceOut",
    "SourceUpdate",
    "TemplateCreate",
    "TemplateOut",
    "TemplateUpdate",
    "TokenPair",
    "TwoFactorSetup",
    "TwoFactorVerify",
    "UserCreate",
    "UserOut",
    "UserUpdate",
    "WatermarkCreate",
    "WatermarkOut",
    "WatermarkUpdate",
]
