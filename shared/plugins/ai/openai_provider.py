"""OpenAI provider (chat completions + embeddings)."""

from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.enums import AIProviderType
from shared.exceptions import AIProviderError
from shared.logging import get_logger
from shared.plugins.ai.base import AIResult, BaseAIProvider, ai_registry

log = get_logger("ai.openai")


@ai_registry.register(AIProviderType.OPENAI.value)
class OpenAIProvider(BaseAIProvider):
    """Rewrite news via OpenAI Chat Completions and embed via embeddings API."""

    provider_type = AIProviderType.OPENAI.value

    def _client(self):  # type: ignore[no-untyped-def]
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("openai package is not installed") from exc
        if not self.api_key:
            raise AIProviderError("OpenAI API key is not configured")
        return AsyncOpenAI(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    async def process(self, title: str | None, text: str) -> AIResult:
        client = self._client()
        try:
            completion = await client.chat.completions.create(
                model=self.model or "gpt-4o-mini",
                temperature=self.profile.temperature,
                max_tokens=self.profile.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.build_system_prompt()},
                    {"role": "user", "content": self.build_user_prompt(title, text)},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        raw = completion.choices[0].message.content or ""
        return self.parse_json_result(raw, title, text)

    async def embed(self, text: str) -> list[float] | None:
        client = self._client()
        try:
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            return list(response.data[0].embedding)
        except Exception as exc:  # noqa: BLE001
            log.warning("openai_embed_failed", error=str(exc))
            return None
