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


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    language: str | None = None
    telegram_id: int | None = None
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
    last_login_at: datetime | None
    created_at: datetime
