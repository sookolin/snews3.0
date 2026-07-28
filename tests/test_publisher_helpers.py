"""Tests for publisher helpers: {link} resolution and custom-emoji fallback."""

from __future__ import annotations

from shared.models.channel import Channel
from shared.plugins.publishers.telegram_publisher import strip_custom_emoji
from shared.services.publisher_service import channel_subscribe_link


def _channel(**kwargs) -> Channel:  # type: ignore[no-untyped-def]
    defaults = dict(id=1, city_id=1, title="Канал", chat_id="-1001234567890")
    defaults.update(kwargs)
    return Channel(**defaults)


def test_link_uses_username_when_available() -> None:
    link = channel_subscribe_link(_channel(username="@kazan_news"))
    assert link == "https://t.me/kazan_news"


def test_link_derives_username_from_chat_id() -> None:
    link = channel_subscribe_link(_channel(chat_id="t.me/kazan_news"))
    assert link == "https://t.me/kazan_news"


def test_link_falls_back_to_private_channel_form() -> None:
    link = channel_subscribe_link(_channel(chat_id="-1001234567890"))
    assert link == "https://t.me/c/1234567890"


def test_link_empty_without_any_identifier() -> None:
    assert channel_subscribe_link(_channel(chat_id="")) == ""


def test_strip_custom_emoji_keeps_fallback_character() -> None:
    """Dropping the premium entity must keep the visible emoji, not delete it."""
    html = 'Привет <tg-emoji emoji-id="5208452345314156636">👉</tg-emoji> мир'
    assert strip_custom_emoji(html) == "Привет 👉 мир"


def test_strip_custom_emoji_leaves_other_markup_untouched() -> None:
    html = "<b>жирный</b> текст"
    assert strip_custom_emoji(html) == html
