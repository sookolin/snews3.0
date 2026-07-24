"""Seed the database with a super admin and sensible default profiles.

Idempotent: running multiple times will not create duplicates.

Usage::

    python -m scripts.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from shared.config import settings
from shared.database import session_scope
from shared.enums import AIProviderType, UserRole
from shared.logging import configure_logging, get_logger
from shared.models.ai import DEFAULT_SYSTEM_PROMPT, AIProfile
from shared.models.template import Template
from shared.models.user import User
from shared.models.watermark import WatermarkProfile
from shared.security import hash_password
from shared.services.settings_service import SettingsService

log = get_logger("seed")


async def seed() -> None:
    configure_logging()
    async with session_scope() as session:
        # ── Super admin ──────────────────────────────────────────────────────
        existing = await session.scalar(
            select(User).where(User.email == settings.first_superadmin_email.lower())
        )
        if existing is None:
            session.add(
                User(
                    email=settings.first_superadmin_email.lower(),
                    full_name="Super Admin",
                    hashed_password=hash_password(settings.first_superadmin_password),
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    language=settings.default_language,
                )
            )
            log.info("superadmin_created", email=settings.first_superadmin_email)
        else:
            log.info("superadmin_exists")

        # ── Default template ─────────────────────────────────────────────────
        if not await session.scalar(select(Template).where(Template.is_default.is_(True))):
            session.add(
                Template(
                    name="Default",
                    is_default=True,
                    header="🔥 <b>{title}</b>",
                    body="{text}",
                    footer=(
                        "Источник: {source}\n————————\n"
                        '👉 <a href="{link}">Подписаться на новости</a>'
                    ),
                    separator="\n\n",
                )
            )
            log.info("default_template_created")

        # ── Default AI profile ───────────────────────────────────────────────
        if not await session.scalar(select(AIProfile).where(AIProfile.is_default.is_(True))):
            session.add(
                AIProfile(
                    name="Default",
                    is_default=True,
                    provider=AIProviderType(settings.default_ai_provider),
                    model=None,
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                    temperature=0.4,
                    max_tokens=2048,
                )
            )
            log.info("default_ai_profile_created")

        # ── Default watermark profile ────────────────────────────────────────
        if not await session.scalar(
            select(WatermarkProfile).where(WatermarkProfile.is_default.is_(True))
        ):
            session.add(
                WatermarkProfile(
                    name="Default",
                    is_default=True,
                    text=settings.app_name,
                    position="bottom-right",
                    opacity=0.7,
                )
            )
            log.info("default_watermark_created")

        await session.flush()
        await SettingsService(session).ensure_defaults()
        await session.commit()
        log.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed())
