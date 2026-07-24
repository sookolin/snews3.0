"""AI provider plugins — unified interface over Claude, OpenAI, Gemini, local.

Each provider implements :class:`BaseAIProvider` and registers under its
:class:`~shared.enums.AIProviderType` value.
"""

from __future__ import annotations

from shared.plugins.ai import anthropic_provider as _anthropic  # noqa: F401,E402
from shared.plugins.ai import gemini_provider as _gemini  # noqa: F401,E402
from shared.plugins.ai import local_provider as _local  # noqa: F401,E402
from shared.plugins.ai import openai_provider as _openai  # noqa: F401,E402
from shared.plugins.ai.base import (
    AIResult,
    BaseAIProvider,
    ai_registry,
)

__all__ = ["AIResult", "BaseAIProvider", "ai_registry"]
