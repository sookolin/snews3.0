"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from shared.enums import UserRole
from shared.schemas.common import ORMModel


class UserCreate(BaseModel):
    """Create a user by linking their Telegram account.

    New accounts are provisioned by an admin who binds a Telegram id (and
    optionally a username). Email/password are set later by the user, so both
    are optional here.
    """

    telegram_id: int
    telegram_username: str | None = None
    role: UserRole = UserRole.REVIEWER
    is_active: bool = True
    language: str = "ru"
    permissions: dict = Field(default_factory=dict)
    #: Restrict this user to only the listed cities (empty = unrestricted).
    city_access: list[int] = Field(default_factory=list)
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    language: str | None = None
    telegram_id: int | None = None
    telegram_username: str | None = None
    permissions: dict | None = None
    city_access: list[int] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    is_banned: bool
    is_2fa_enabled: bool
    language: str
    telegram_id: int | None
    telegram_username: str | None = None
    photo_url: str | None
    permissions: dict
    city_access: list[int] = Field(default_factory=list)
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
