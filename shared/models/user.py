"""User & role model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin

# Note: shared.enums.UserRole import intentionally removed from column typing
# below — see the `role` column docstring for why it's a plain string.
from shared.db_types import JSONB


class User(Base, TimestampMixin):
    """Web-panel user with a role and optional 2FA."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Plain string, NOT a SQLAlchemy Enum(UserRole, ...): custom roles created
    # via Users → "Права ролей" / "Добавить роль" are arbitrary strings not
    # known to the ``UserRole`` Python enum, so a strict enum column would
    # reject them with a raw ``LookupError`` at flush time (uncaught -> 500).
    # Validity is enforced at the service layer (``UserService``) against the
    # live role catalog (built-in ``UserRole`` values + ``roles.custom``).
    role: Mapped[str] = mapped_column(
        String(32),
        default="reviewer",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 2FA
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64))

    # Telegram linkage (for bot moderation permission checks + login)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    # Legacy external accounts (OAuth login via VK/Yandex) — retained for
    # backwards compatibility; no longer used for new sign-ins.
    yandex_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    vk_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # Avatar URL fetched from the OAuth provider (Telegram / VK / Yandex).
    # Stored as-is; the UI falls back to initials when absent.
    photo_url: Mapped[str | None] = mapped_column(String(1024))

    # Per-user permission overrides on top of the role:
    #   {"grant": ["news:publish"], "deny": ["news:delete"]}
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # City access restriction: when non-empty, the user only sees/moderates
    # news for these cities (by id). Empty/None means unrestricted (sees
    # every city) — this is the default for existing roles, including
    # super admin, who always has full access regardless of this field.
    city_access: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)

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
