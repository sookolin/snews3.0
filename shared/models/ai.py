"""AI profile model — an editable configuration for an AI provider."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, TimestampMixin
from shared.enums import AIProviderType

DEFAULT_SYSTEM_PROMPT = (
    "Ты — профессиональный редактор новостей. Перепиши предоставленный текст "
    "новости, не искажая факты. Исправь ошибки, структурируй текст, сделай "
    "единый стиль и красивый заголовок. Верни результат строго в формате JSON: "
    '{"title": "...", "text": "..."}. Текст должен быть готов к публикации в '
    "Telegram и использовать допустимые HTML-теги (<b>, <i>, <a>)."
)


class AIProfile(Base, TimestampMixin):
    """Editable AI processing profile (prompt, model, temperature…)."""

    __tablename__ = "ai_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    provider: Mapped[AIProviderType] = mapped_column(
        Enum(AIProviderType, native_enum=False, length=32),
        default=AIProviderType.ANTHROPIC,
        nullable=False,
    )
    model: Mapped[str | None] = mapped_column(String(128))

    # Fully DB-configurable credentials (no .env needed).
    api_key: Mapped[str | None] = mapped_column(String(512))
    # Custom base URL / endpoint (OpenAI-compatible, Gemini proxy, local LLM…).
    base_url: Mapped[str | None] = mapped_column(String(512))
    # Embedding model name (optional; provider-specific default otherwise).
    embedding_model: Mapped[str | None] = mapped_column(String(128))

    system_prompt: Mapped[str] = mapped_column(Text, default=DEFAULT_SYSTEM_PROMPT, nullable=False)
    # Extra instructions appended to system prompt (tone, style…)
    instructions: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(128))
    style: Mapped[str | None] = mapped_column(String(128))

    temperature: Mapped[float] = mapped_column(Float, default=0.4, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)

    # Whether to also produce an embedding for semantic dedup
    generate_embeddings: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AIProfile {self.id} {self.name} {self.provider}>"
