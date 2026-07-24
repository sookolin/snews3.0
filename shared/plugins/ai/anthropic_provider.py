"""Anthropic Claude AI provider."""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.enums import AIProviderType
from shared.exceptions import AIProviderError
from shared.logging import get_logger
from shared.plugins.ai.base import AIResult, BaseAIProvider, ai_registry

log = get_logger("ai.anthropic")


@ai_registry.register(AIProviderType.ANTHROPIC.value)
class AnthropicProvider(BaseAIProvider):
    """Rewrite news via Anthropic's Messages API."""

    provider_type = AIProviderType.ANTHROPIC.value

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    async def process(self, title: str | None, text: str) -> AIResult:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("anthropic package is not installed") from exc

        if not self.api_key:
            raise AIProviderError("Anthropic API key is not configured")

        client = AsyncAnthropic(api_key=self.api_key)
        try:
            message = await client.messages.create(
                model=self.model or "claude-3-5-sonnet-latest",
                max_tokens=self.profile.max_tokens,
                temperature=self.profile.temperature,
                system=self.build_system_prompt(),
                messages=[{"role": "user", "content": self.build_user_prompt(title, text)}],
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Anthropic request failed: {exc}") from exc

        raw = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        return self.parse_json_result(raw, title, text)
