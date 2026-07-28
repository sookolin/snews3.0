"""Shared enumerations used across models, schemas and services."""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Hierarchical roles. Higher position => more power (see PERMISSIONS)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    EDITOR = "editor"
    REVIEWER = "reviewer"


class SourceType(str, Enum):
    RSS = "rss"
    TELEGRAM = "telegram"
    WEBSITE = "website"
    API = "api"
    HTML = "html"


class ParserEngine(str, Enum):
    """Engine used to fetch/parse a website source."""

    AUTO = "auto"
    BEAUTIFULSOUP = "beautifulsoup"
    LXML = "lxml"
    PLAYWRIGHT = "playwright"


class NewsStatus(str, Enum):
    """Lifecycle of a news item.

    Flow: ``PROCESSING`` (AI rewriting) → ``PENDING`` (awaiting moderation) →
    ``APPROVED`` (cleared, waiting for its publication slot) or ``SCHEDULED``
    (queued for a specific time) → ``PUBLISHED`` (live in the channel).
    ``WITHDRAWN`` means it was published and then taken down; it can be
    published again. ``REJECTED`` and ``FAILED`` are terminal.
    """

    PROCESSING = "processing"    # being handled by AI
    PENDING = "pending"          # awaiting moderation
    APPROVED = "approved"        # approved, waiting for its publication slot
    SCHEDULED = "scheduled"      # queued for a specific time
    PUBLISHED = "published"      # live in the channel
    WITHDRAWN = "withdrawn"      # was published, then removed from the channel
    REJECTED = "rejected"
    FAILED = "failed"


class NewsOrigin(str, Enum):
    PARSER = "parser"  # discovered by a source parser
    USER = "user"  # submitted by a Telegram user


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"  # gif
    DOCUMENT = "document"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"


class AIProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    LOCAL = "local"


class ChannelPublishMode(str, Enum):
    IMMEDIATE = "immediate"  # publish right after approval
    DRAFT = "draft"  # keep as draft
    SCHEDULED = "scheduled"  # publish at scheduled_at
    MANUAL = "manual"  # publish only on manual action


class TemplateFormat(str, Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    TELEGRAM_HTML = "telegram_html"


class AdStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


class NotificationChannel(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"


class Permission(str, Enum):
    """Fine-grained permissions checked by the API layer."""

    # Cities
    CITY_VIEW = "city:view"
    CITY_MANAGE = "city:manage"
    # Sources
    SOURCE_VIEW = "source:view"
    SOURCE_MANAGE = "source:manage"
    # News
    NEWS_VIEW = "news:view"
    NEWS_EDIT = "news:edit"
    NEWS_MODERATE = "news:moderate"  # approve/reject
    NEWS_PUBLISH = "news:publish"
    NEWS_DELETE = "news:delete"
    # Templates / watermark / AI / settings
    TEMPLATE_MANAGE = "template:manage"
    WATERMARK_MANAGE = "watermark:manage"
    AI_MANAGE = "ai:manage"
    SETTINGS_MANAGE = "settings:manage"
    # Telegram channels
    CHANNEL_MANAGE = "channel:manage"
    # Users / roles
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"
    # System
    LOGS_VIEW = "logs:view"
    BACKUP_MANAGE = "backup:manage"
    MONITORING_VIEW = "monitoring:view"


# Role → set of permissions. Super admin gets everything implicitly.
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.SUPER_ADMIN: set(Permission),
    UserRole.ADMIN: set(Permission) - {Permission.BACKUP_MANAGE},  # admin can do almost everything
    UserRole.MODERATOR: {
        Permission.CITY_VIEW,
        Permission.SOURCE_VIEW,
        Permission.NEWS_VIEW,
        Permission.NEWS_EDIT,
        Permission.NEWS_MODERATE,
        Permission.NEWS_PUBLISH,
        Permission.MONITORING_VIEW,
    },
    UserRole.EDITOR: {
        Permission.CITY_VIEW,
        Permission.SOURCE_VIEW,
        Permission.NEWS_VIEW,
        Permission.NEWS_EDIT,
        Permission.TEMPLATE_MANAGE,
    },
    UserRole.REVIEWER: {
        Permission.CITY_VIEW,
        Permission.NEWS_VIEW,
    },
}


def permissions_for_role(role: UserRole) -> set[Permission]:
    """Return the effective permission set for a role."""
    return ROLE_PERMISSIONS.get(role, set())
