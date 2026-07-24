# Extending CityNews with plugins

The system is built around three plugin registries so new capabilities can be
added without modifying existing code.

## New parser

```python
# shared/plugins/parsers/my_parser.py
from shared.enums import SourceType
from shared.plugins.parsers.base import BaseParser, ParsedItem, parser_registry

@parser_registry.register("my_type")   # matches Source.type value
class MyParser(BaseParser):
    source_type = "my_type"

    async def fetch(self) -> list[ParsedItem]:
        # self.source gives you url, headers, cookies, auth, selectors, timeout…
        return [ParsedItem(title="…", text="…", url="…", guid="…")]
```

Import it in `shared/plugins/parsers/__init__.py` (or add auto-discovery). Add
`my_type` to `SourceType` if it should be selectable in the UI.

## New AI provider

```python
# shared/plugins/ai/my_provider.py
from shared.plugins.ai.base import AIResult, BaseAIProvider, ai_registry

@ai_registry.register("my_ai")
class MyProvider(BaseAIProvider):
    provider_type = "my_ai"

    async def process(self, title, text) -> AIResult:
        raw = await call_my_model(self.build_system_prompt(),
                                  self.build_user_prompt(title, text))
        return self.parse_json_result(raw, title, text)

    async def embed(self, text):        # optional, for semantic dedup
        return await my_embeddings(text)
```

Add the key to `AIProviderType` and wire an API key in `AIService._api_key_for`.

## New publisher

```python
# shared/plugins/publishers/my_publisher.py
from shared.plugins.publishers.base import (
    BasePublisher, PublishRequest, PublishResult, publisher_registry,
)

@publisher_registry.register("my_channel")
class MyPublisher(BasePublisher):
    publisher_type = "my_channel"

    async def publish(self, request: PublishRequest) -> PublishResult:
        ...
        return PublishResult(success=True, message_ids=[123])
```

## Why this works

`Registry` (in `shared/plugins/registry.py`) maps string keys to classes.
Services resolve the right implementation at runtime (`registry.get(key)`), so
adding a plugin never touches the pipeline, publisher service or API layer —
satisfying the Open/Closed Principle.
