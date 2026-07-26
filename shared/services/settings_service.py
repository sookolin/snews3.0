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
    "dedup.embedding_threshold": {"value": 0.92, "category": "dedup"},
    "dedup.lookback_days": {"value": 14, "category": "dedup"},
    "matching.min_score": {"value": 0.3, "category": "matching"},
    "pipeline.auto_publish_on_approve": {"value": True, "category": "pipeline"},
    "pipeline.require_moderation": {"value": True, "category": "pipeline"},
    "notifications.email_enabled": {"value": False, "category": "notifications"},
    "notifications.webhook_url": {"value": "", "category": "notifications"},
    "ui.default_language": {"value": "ru", "category": "ui"},
    "site.favicon_url": {"value": "", "category": "ui"},
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
