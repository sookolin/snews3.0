"""AI profile schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.enums import AIProviderType
from shared.schemas.common import ORMModel


class AIProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False
    is_active: bool = True
    provider: AIProviderType = AIProviderType.ANTHROPIC
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    embedding_model: str | None = None
    system_prompt: str
    instructions: str | None = None
    tone: str | None = None
    style: str | None = None
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=32000)
    generate_embeddings: bool = True


class AIProfileCreate(AIProfileBase):
    pass


class AIProfileUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    provider: AIProviderType | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    embedding_model: str | None = None
    system_prompt: str | None = None
    instructions: str | None = None
    tone: str | None = None
    style: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=32000)
    generate_embeddings: bool | None = None


class AIProfileOut(ORMModel):
    id: int
    name: str
    is_default: bool
    is_active: bool
    provider: AIProviderType
    model: str | None
    base_url: str | None
    embedding_model: str | None
    # api_key is write-only; expose only whether it is set.
    has_api_key: bool = False
    system_prompt: str
    instructions: str | None
    tone: str | None
    style: str | None
    temperature: float
    max_tokens: int
    generate_embeddings: bool
    created_at: datetime

    @classmethod
    def from_model(cls, obj: object) -> "AIProfileOut":
        data = cls.model_validate(obj)
        data.has_api_key = bool(getattr(obj, "api_key", None))
        return data