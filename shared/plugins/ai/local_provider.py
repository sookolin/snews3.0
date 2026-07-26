"""Local LLM provider (OpenAI-compatible endpoint, e.g. Ollama / vLLM / LM Studio)."""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.config import settings
from shared.enums import AIProviderType
from shared.exceptions import AIProviderError
from shared.logging import get_logger
from shared.plugins.ai.base import AIResult, BaseAIProvider, ai_registry

log = get_logger("ai.local")


@ai_registry.register(AIProviderType.LOCAL.value)
class LocalProvider(BaseAIProvider):
    """Rewrite news via a local OpenAI-compatible endpoint."""

    provider_type = AIProviderType.LOCAL.value

    def _client(self):  # type: ignore[no-untyped-def]
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("openai package is not installed") from exc
        # Local endpoints usually ignore the key, but the SDK requires a value.
        return AsyncOpenAI(
            api_key=self.api_key or "local",
            base_url=self.base_url or settings.local_llm_base_url,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def process(self, title: str | None, text: str) -> AIResult:
        client = self._client()
        try:
            completion = await client.chat.completions.create(
                model=self.model or settings.local_llm_model,
                temperature=self.profile.temperature,
                max_tokens=self.profile.max_tokens,
                messages=[
                    {"role": "system", "content": self.build_system_prompt()},
                    {"role": "user", "content": self.build_user_prompt(title, text)},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Local LLM request failed: {exc}") from exc

        raw = completion.choices[0].message.content or ""
        return self.parse_json_result(raw, title, text)
