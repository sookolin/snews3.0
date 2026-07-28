"""Base AI provider interface and helpers."""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass

from shared.models.ai import AIProfile
from shared.plugins.registry import Registry


@dataclass
class AIResult:
    """Result of AI news processing."""

    title: str
    text: str
    emoji: str | None = None
    embedding: list[float] | None = None


class BaseAIProvider(abc.ABC):
    """Abstract AI provider producing a rewritten title/text (+ optional embedding)."""

    provider_type: str = ""

    def __init__(self, profile: AIProfile, api_key: str, model: str | None) -> None:
        self.profile = profile
        self.api_key = api_key
        self.model = model or ""

    @property
    def base_url(self) -> str | None:
        """Custom endpoint configured on the profile (DB), if any."""
        return (getattr(self.profile, "base_url", None) or "").strip() or None

    @property
    def embedding_model(self) -> str | None:
        return (getattr(self.profile, "embedding_model", None) or "").strip() or None

    def build_system_prompt(self) -> str:
        """Combine the profile prompt with tone/style/extra instructions."""
        parts = [self.profile.system_prompt]
        if self.profile.tone:
            parts.append(f"Тон: {self.profile.tone}.")
        if self.profile.style:
            parts.append(f"Стиль: {self.profile.style}.")
        if self.profile.instructions:
            parts.append(self.profile.instructions)
        return "\n\n".join(p for p in parts if p)

    def build_user_prompt(self, title: str | None, text: str) -> str:
        header = f"Заголовок: {title}\n\n" if title else ""
        want_emoji = getattr(self.profile, "auto_emoji", False)
        emoji_rule = (
            ' Также подбери один эмодзи, подходящий по смыслу к заголовку, и верни его '
            'в поле "emoji".'
            if want_emoji
            else ""
        )
        return (
            f"{header}Текст новости:\n{text}\n\n"
            "Требования: заголовок верни обычным текстом БЕЗ HTML-тегов и без эмодзи в начале. "
            "В тексте можно использовать теги <b>, <i>, <a>." + emoji_rule + "\n"
            'Верни строго JSON вида {"title": "...", "text": "...", "emoji": "..."} без пояснений.'
        )

    @staticmethod
    def parse_json_result(raw: str, fallback_title: str | None, fallback_text: str) -> AIResult:
        """Parse a model's JSON response, tolerating code fences / extra text."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            data = json.loads(cleaned)
            emoji = str(data.get("emoji") or "").strip() or None
            return AIResult(
                title=str(data.get("title") or fallback_title or "").strip(),
                text=str(data.get("text") or fallback_text).strip(),
                emoji=emoji,
            )
        except (json.JSONDecodeError, AttributeError):
            # Model returned plain text — use it as the body.
            return AIResult(title=fallback_title or "", text=raw.strip() or fallback_text)

    @abc.abstractmethod
    async def process(self, title: str | None, text: str) -> AIResult:
        """Rewrite the news and optionally attach an embedding."""
        raise NotImplementedError

    async def embed(self, text: str) -> list[float] | None:
        """Return an embedding for ``text`` if supported, else ``None``."""
        return None


ai_registry: Registry[type[BaseAIProvider]] = Registry("ai_provider")
