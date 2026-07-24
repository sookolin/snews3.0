"""Lightweight i18n message catalog for the interface & system messages.

UI translations for the frontend live in ``frontend/`` (next-intl). This module
covers backend/bot-generated messages. Additional languages can be added at
runtime through the database (``Setting`` key ``i18n.<lang>``) which is merged
over these defaults by :func:`load_runtime_translations`.
"""

from __future__ import annotations

from shared.config import settings

# Base catalog. Keys are dotted identifiers.
CATALOG: dict[str, dict[str, str]] = {
    "ru": {
        "bot.start": "Привет! Я помогу предложить новость. Используйте /suggest.",
        "bot.choose_city": "Выберите город:",
        "bot.enter_text": "Отправьте текст новости:",
        "bot.attach_media": "Прикрепите медиа (фото/видео/документ) или нажмите «Готово».",
        "bot.anonymous_q": "Опубликовать анонимно?",
        "bot.submitted": "Спасибо! Новость отправлена на модерацию.",
        "bot.cancelled": "Отменено.",
        "bot.done": "Готово",
        "bot.yes": "Да",
        "bot.no": "Нет",
        "moderation.approve": "✅ Одобрить",
        "moderation.reject": "❌ Отклонить",
        "moderation.edit": "✏️ Редактировать",
        "moderation.open_admin": "🖥 Админка",
        "moderation.source": "🔗 Источник",
        "moderation.original": "📄 Оригинал",
        "moderation.spoiler": "🙈 Спойлер",
        "moderation.approved": "Новость одобрена.",
        "moderation.rejected": "Новость отклонена.",
        "moderation.no_permission": "Недостаточно прав.",
    },
    "en": {
        "bot.start": "Hi! I can help you suggest news. Use /suggest.",
        "bot.choose_city": "Choose a city:",
        "bot.enter_text": "Send the news text:",
        "bot.attach_media": "Attach media (photo/video/document) or press “Done”.",
        "bot.anonymous_q": "Publish anonymously?",
        "bot.submitted": "Thank you! Your news was sent to moderation.",
        "bot.cancelled": "Cancelled.",
        "bot.done": "Done",
        "bot.yes": "Yes",
        "bot.no": "No",
        "moderation.approve": "✅ Approve",
        "moderation.reject": "❌ Reject",
        "moderation.edit": "✏️ Edit",
        "moderation.open_admin": "🖥 Admin",
        "moderation.source": "🔗 Source",
        "moderation.original": "📄 Original",
        "moderation.spoiler": "🙈 Spoiler",
        "moderation.approved": "News approved.",
        "moderation.rejected": "News rejected.",
        "moderation.no_permission": "Insufficient permissions.",
    },
}

# Runtime overrides merged from DB (populated by backend on startup).
_runtime: dict[str, dict[str, str]] = {}


def load_runtime_translations(overrides: dict[str, dict[str, str]]) -> None:
    """Merge database-provided translations over the base catalog."""
    for lang, mapping in overrides.items():
        _runtime.setdefault(lang, {}).update(mapping)


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    """Translate ``key`` for ``lang`` (falls back to default language then key)."""
    lang = lang or settings.default_language
    for source in (
        _runtime.get(lang),
        CATALOG.get(lang),
        _runtime.get(settings.default_language),
        CATALOG.get(settings.default_language),
    ):
        if source and key in source:
            value = source[key]
            return value.format(**kwargs) if kwargs else value
    return key
