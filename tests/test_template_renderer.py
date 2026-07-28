"""Unit tests for template rendering."""

from __future__ import annotations

from shared.enums import TemplateFormat
from shared.models.template import Template
from shared.services.template_renderer import TemplateRenderer


def _template(**kwargs) -> Template:  # type: ignore[no-untyped-def]
    defaults = dict(
        id=1,
        name="t",
        is_default=True,
        is_active=True,
        format=TemplateFormat.TELEGRAM_HTML,
        header="🔥 <b>{title}</b>",
        body="{text}",
        footer='Источник: {source}\n👉 <a href="{link}">Подписаться</a>',
        separator="\n\n",
        variables={},
        disable_web_preview=True,
        subscribe_link="https://t.me/mychannel",
    )
    defaults.update(kwargs)
    return Template(**defaults)


def test_render_basic() -> None:
    out = TemplateRenderer().render(
        _template(),
        title="Заголовок",
        text="Текст новости",
        source="РИА",
        source_url="https://ria.ru/1",
        city="Казань",
    )
    assert "🔥 <b>Заголовок</b>" in out
    assert "Текст новости" in out
    # The source is rendered as a hyperlink to the original publication.
    assert 'Источник: <a href="https://ria.ru/1">РИА</a>' in out
    assert "https://t.me/mychannel" in out


def test_source_without_url_stays_plain() -> None:
    out = TemplateRenderer().render(
        _template(), title="T", text="B", source="РИА", source_url="",
    )
    assert "Источник: РИА" in out
    assert "<a href" not in out.split("Источник:")[1].split("\n")[0]


def test_missing_placeholder_is_empty_not_error() -> None:
    out = TemplateRenderer().render(
        _template(body="{text} {nonexistent}"),
        title="T",
        text="Body",
        source="S",
    )
    assert "Body" in out


def test_renderer_preserves_markup() -> None:
    """The renderer must not escape markup: Telegram needs real <b>/<i> tags.

    Unsafe tags are removed later by the Telegram HTML sanitizer, not here.
    """
    out = TemplateRenderer().render(
        _template(format=TemplateFormat.TELEGRAM_HTML, header="{title}", body="{text}", footer=""),
        title="Заголовок",
        text="<b>жирный</b> и <i>курсив</i>",
    )
    assert "<b>жирный</b>" in out
    assert "<i>курсив</i>" in out


def test_sanitizer_strips_unsafe_tags_from_rendered_output() -> None:
    from shared.services.html_sanitizer import sanitize_telegram_html

    out = TemplateRenderer().render(
        _template(format=TemplateFormat.HTML, header="{title}", body="{text}", footer=""),
        title="<script>alert(1)</script>",
        text="<b>ok</b>",
    )
    safe = sanitize_telegram_html(out)
    assert "<script>" not in safe
    assert "<b>ok</b>" in safe


def test_custom_emoji_is_independent_of_post_emoji() -> None:
    """{custom_emoji} renders the premium tag; {emoji} stays the post accent."""
    out = TemplateRenderer().render(
        _template(header="{custom_emoji} {emoji} {title}", body="", footer="",
                  custom_emoji_id="5208452345314156636"),
        title="T", text="", emoji="🚗",
    )
    assert 'tg-emoji emoji-id="5208452345314156636"' in out
    # The per-post emoji is a separate placeholder and must still be present.
    assert "🚗" in out


def test_city_link_overrides_template_subscribe_link() -> None:
    """{link} follows the city's channel so one template serves every city."""
    out = TemplateRenderer().render(
        _template(header="", body="", footer='<a href="{link}">Подписаться</a>'),
        title="T",
        text="",
        link="https://t.me/kazan_news",
    )
    assert 'href="https://t.me/kazan_news"' in out
    assert "mychannel" not in out


def test_link_falls_back_to_template_when_city_link_unknown() -> None:
    out = TemplateRenderer().render(
        _template(header="", body="", footer='<a href="{link}">Подписаться</a>'),
        title="T",
        text="",
    )
    assert 'href="https://t.me/mychannel"' in out


def test_no_custom_emoji_tag_without_id() -> None:
    out = TemplateRenderer().render(
        _template(header="{custom_emoji}{title}", body="", footer=""),
        title="T", text="",
    )
    assert "tg-emoji" not in out
