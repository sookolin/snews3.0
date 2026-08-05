"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from shared.schemas.common import ORMModel


class UserCreate(BaseModel):
    """Create a user by linking their Telegram account.

    New accounts are provisioned by an admin who binds a Telegram id (and
    optionally a username). Email/password are set later by the user, so both
    are optional here.

    ``role`` is a plain string rather than the ``UserRole`` enum because
    custom roles (created in Users → Права ролей) are not known statically;
    the API validates it against the live role catalog instead.
    """

    telegram_id: int
    telegram_username: str | None = None
    role: str = "reviewer"
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
    role: str | None = None
    is_active: bool | None = None
    language: str | None = None
    telegram_id: int | None = None
    telegram_username: str | None = None
    permissions: dict | None = None
    city_access: list[int] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    # Plain str, not EmailStr: accounts created by binding only a Telegram
    # id get a synthesized placeholder address like
    # "tg123@telegram.local" (see UserService.create) until the user sets
    # a real email themselves. The ".local" TLD is a reserved/special-use
    # domain that email-validator (used by EmailStr) rejects, which broke
    # serializing the response right after creating such a user even
    # though the row was saved fine. Output serialization doesn't need to
    # re-validate the address, so a plain string is safe here.
    email: str
    full_name: str | None
    role: str
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
