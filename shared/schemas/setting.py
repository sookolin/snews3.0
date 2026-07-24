"""Setting & dashboard schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from shared.schemas.common import ORMModel


class SettingOut(ORMModel):
    key: str
    value: Any
    category: str
    description: str | None
    is_secret: bool


class SettingUpdate(BaseModel):
    value: Any
    description: str | None = None
    category: str | None = None
