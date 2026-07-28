"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from shared.enums import UserRole
from shared.schemas.common import ORMModel


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: UserRole = UserRole.REVIEWER
    is_active: bool = True
    language: str = "ru"
    telegram_id: int | None = None
    yandex_id: str | None = None
    vk_id: str | None = None
    permissions: dict = Field(default_factory=dict)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    language: str | None = None
    telegram_id: int | None = None
    yandex_id: str | None = None
    vk_id: str | None = None
    permissions: dict | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    is_2fa_enabled: bool
    language: str
    telegram_id: int | None
    yandex_id: str | None
    vk_id: str | None
    permissions: dict
    last_login_at: datetime | None
    created_at: datetime


class PermissionInfo(BaseModel):
    """A single permission with a human-readable description."""

    value: str
    label: str
    group: str


class RolePermissions(BaseModel):
    role: str
    permissions: list[str]
