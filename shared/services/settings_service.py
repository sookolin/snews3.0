"""Settings service — typed access to DB-stored runtime settings with caching."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.setting import Setting

# Default runtime settings created on first run / referenced as fallbacks.
DEFAULTS: dict[str, dict[str, Any]] = {
    "dedup.simhash_max_distance": {"value": 3, "category": "dedup"},
    "dedup.text_similarity_threshold": {"value": 0.9, "category": "dedup"},
    "dedup.title_similarity_threshold": {"value": 0.72, "category": "dedup"},
    "dedup.embedding_threshold": {"value": 0.92, "category": "dedup"},
    "dedup.lookback_days": {"value": 14, "category": "dedup"},
    "matching.min_score": {"value": 0.3, "category": "matching"},
    "pipeline.auto_publish_on_approve": {"value": True, "category": "pipeline"},
    "pipeline.require_moderation": {"value": True, "category": "pipeline"},
    # Minutes between consecutive automatic publications (0 = no spacing).
    "pipeline.publish_interval_minutes": {"value": 5, "category": "pipeline"},
    # Ignore items older than this when parsing (real-time mode, 0 = disabled).
    "pipeline.max_item_age_minutes": {"value": 30, "category": "pipeline"},
    # Keep items that match no monitored city as world news (else drop them).
    "pipeline.keep_world_news": {"value": True, "category": "pipeline"},
    "notifications.email_enabled": {"value": False, "category": "notifications"},
    "notifications.webhook_url": {"value": "", "category": "notifications"},
    "ui.default_language": {"value": "ru", "category": "ui"},
    "site.favicon_url": {"value": "", "category": "ui"},
    "bot.username": {"value": "", "category": "telegram"},
    # Separate moderation topic for world/federal news (like a city topic).
    "telegram.world_topic_id": {"value": 0, "category": "telegram"},
    # Display timezone offset (hours) for moderator-facing timestamps.
    "ui.timezone_offset_hours": {"value": 3, "category": "ui"},
    # Layout of the moderation card in the topic. Empty = built-in layout.
    # Placeholders: {post} {title} {id} {place} {city} {score} {source}
    # {source_time} {processed_at} {moderator} {reply_to} {status} {url}
    "moderation.card_template": {"value": "", "category": "telegram"},
    # Email notifications.
    "notifications.email_to": {"value": "", "category": "notifications"},
    "notifications.smtp_host": {"value": "", "category": "notifications"},
    "notifications.smtp_port": {"value": 587, "category": "notifications"},
    "notifications.smtp_user": {"value": "", "category": "notifications"},
    "notifications.smtp_password": {"value": "", "category": "notifications"},
    "notifications.smtp_from": {"value": "", "category": "notifications"},
}


class SettingsService:
    """Read/write runtime settings stored in the ``settings`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str, default: Any = None) -> Any:
        row = await self.session.get(Setting, key)
        if row is not None:
            return row.value
        if key in DEFAULTS:
            return DEFAULTS[key]["value"]
        return default

    async def get_many(self, prefix: str | None = None) -> dict[str, Any]:
        stmt = select(Setting)
        if prefix:
            stmt = stmt.where(Setting.key.startswith(prefix))
        rows = (await self.session.scalars(stmt)).all()
        result = {row.key: row.value for row in rows}
        # Fill in defaults not yet persisted.
        for key, meta in DEFAULTS.items():
            if (prefix is None or key.startswith(prefix)) and key not in result:
                result[key] = meta["value"]
        return result

    async def set(
        self,
        key: str,
        value: Any,
        *,
        category: str = "general",
        description: str | None = None,
        is_secret: bool = False,
    ) -> None:
        existing = await self.session.get(Setting, key)
        if existing is None:
            self.session.add(
                Setting(
                    key=key,
                    value=value,
                    category=category,
                    description=description,
                    is_secret=is_secret,
                )
            )
        else:
            existing.value = value
            existing.category = category
            if description is not None:
                existing.description = description
        await self.session.flush()

    async def ensure_defaults(self) -> None:
        """Persist any missing default settings."""
        existing = set((await self.session.scalars(select(Setting.key))).all())
        for key, meta in DEFAULTS.items():
            if key not in existing:
                await self.set(key, meta["value"], category=meta.get("category", "general"))
