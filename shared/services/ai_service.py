"""AI service — resolves an AI profile and delegates to the right provider plugin."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.enums import AIProviderType
from shared.exceptions import AIProviderError
from shared.models.ai import AIProfile
from shared.plugins.ai import AIResult, ai_registry
from shared.plugins.ai.base import BaseAIProvider


def _api_key_for(provider: AIProviderType) -> str:
    """Fallback API key from .env (used only when the profile has none set)."""
    return {
        AIProviderType.ANTHROPIC: settings.anthropic_api_key,
        AIProviderType.OPENAI: settings.openai_api_key,
        AIProviderType.GEMINI: settings.gemini_api_key,
        AIProviderType.LOCAL: "",
    }.get(provider, "")


def _default_model_for(provider: AIProviderType) -> str:
    return {
        AIProviderType.ANTHROPIC: settings.anthropic_model,
        AIProviderType.OPENAI: settings.openai_model,
        AIProviderType.GEMINI: settings.gemini_model,
        AIProviderType.LOCAL: settings.local_llm_model,
    }.get(provider, "")


class AIService:
    """High-level façade for AI processing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(self, profile_id: int | None = None) -> AIProfile:
        """Return the requested profile, or the default active one."""
        if profile_id is not None:
            profile = await self.session.get(AIProfile, profile_id)
            if profile is not None:
                return profile
        profile = await self.session.scalar(
            select(AIProfile)
            .where(AIProfile.is_default.is_(True), AIProfile.is_active.is_(True))
            .limit(1)
        )
        if profile is None:
            profile = await self.session.scalar(
                select(AIProfile).where(AIProfile.is_active.is_(True)).limit(1)
            )
        if profile is None:
            raise AIProviderError("No active AI profile configured")
        return profile

    def _build_provider(self, profile: AIProfile) -> BaseAIProvider:
        provider_cls = ai_registry.get(profile.provider.value)
        model = profile.model or _default_model_for(profile.provider)
        # Prefer credentials stored on the profile (DB), fall back to .env.
        api_key = (profile.api_key or "").strip() or _api_key_for(profile.provider)
        return provider_cls(profile, api_key, model)

    async def process(
        self, title: str | None, text: str, profile_id: int | None = None
    ) -> tuple[AIResult, AIProfile]:
        """Rewrite the news and (optionally) generate an embedding."""
        profile = await self.get_profile(profile_id)
        provider = self._build_provider(profile)

        result = await provider.process(title, text)
        if profile.generate_embeddings:
            result.embedding = await provider.embed(f"{result.title}\n{result.text}")
        return result, profile

    async def embed(self, text: str, profile_id: int | None = None) -> list[float] | None:
        """Generate an embedding using the profile's provider (best-effort)."""
        profile = await self.get_profile(profile_id)
        provider = self._build_provider(profile)
        return await provider.embed(text)
