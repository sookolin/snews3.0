"""Watermark schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.schemas.common import ORMModel


class WatermarkBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False
    is_active: bool = True
    logo_path: str | None = None
    text: str | None = None
    position: str = Field(default="bottom-right")
    margin_x: int = 20
    margin_y: int = 20
    scale: float = Field(default=0.18, ge=0.01, le=1.0)
    opacity: float = Field(default=0.75, ge=0.0, le=1.0)
    font_size: int = 32
    color: str = "#FFFFFF"
    shadow: bool = True
    shadow_color: str = "#000000"


class WatermarkCreate(WatermarkBase):
    pass


class WatermarkUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    logo_path: str | None = None
    text: str | None = None
    position: str | None = None
    margin_x: int | None = None
    margin_y: int | None = None
    scale: float | None = Field(default=None, ge=0.01, le=1.0)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    font_size: int | None = None
    color: str | None = None
    shadow: bool | None = None
    shadow_color: str | None = None


class WatermarkOut(ORMModel):
    id: int
    name: str
    is_default: bool
    is_active: bool
    logo_path: str | None
    text: str | None
    position: str
    margin_x: int
    margin_y: int
    scale: float
    opacity: float
    font_size: int
    color: str
    shadow: bool
    shadow_color: str
    created_at: datetime
