"""Google Gemini provider."""

from __future__ import annotations

import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.enums import AIProviderType
from shared.exceptions import AIProviderError
from shared.logging import get_logger
from shared.plugins.ai.base import AIResult, BaseAIProvider, ai_registry

log = get_logger("ai.gemini")


@ai_registry.register(AIProviderType.GEMINI.value)
class GeminiProvider(BaseAIProvider):
    """Rewrite news via Google Generative AI (Gemini)."""

    provider_type = AIProviderType.GEMINI.value

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    async def process(self, title: str | None, text: str) -> AIResult:
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("google-generativeai is not installed") from exc

        if not self.api_key:
            raise AIProviderError("Gemini API key is not configured")

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model or "gemini-1.5-flash",
            system_instruction=self.build_system_prompt(),
            generation_config={
                "temperature": self.profile.temperature,
                "max_output_tokens": self.profile.max_tokens,
                "response_mime_type": "application/json",
            },
        )

        def _call() -> str:
            response = model.generate_content(self.build_user_prompt(title, text))
            return response.text or ""

        try:
            raw = await asyncio.to_thread(_call)
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

        return self.parse_json_result(raw, title, text)

    async def embed(self, text: str) -> list[float] | None:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            def _embed() -> list[float]:
                result = genai.embed_content(model="models/text-embedding-004", content=text[:8000])
                return list(result["embedding"])

            return await asyncio.to_thread(_embed)
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini_embed_failed", error=str(exc))
            return None
