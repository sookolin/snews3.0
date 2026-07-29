"""User & role model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin
from shared.db_types import JSONB
from shared.enums import UserRole


class User(Base, TimestampMixin):
    """Web-panel user with a role and optional 2FA."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=32),
        default=UserRole.REVIEWER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 2FA
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64))

    # Telegram linkage (for bot moderation permission checks)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)

    # Linked external accounts (OAuth login)
    yandex_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    vk_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # Per-user permission overrides on top of the role:
    #   {"grant": ["news:publish"], "deny": ["news:delete"]}
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Preferences
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    # Notification preferences, edited in the personal cabinet:
    #   {"push": {"news_pending": true, ...},
    #    "bot": {"login": true, "daily_stats": true, "daily_time": "09:00"}}
    notify_prefs: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Web Push subscriptions (PWA / iOS home-screen), one entry per device:
    #   [{"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}]
    push_subscriptions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id} {self.email} {self.role}>"
