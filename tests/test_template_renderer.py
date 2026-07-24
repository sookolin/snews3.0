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
    assert "Источник: РИА" in out
    assert "https://t.me/mychannel" in out


def test_missing_placeholder_is_empty_not_error() -> None:
    out = TemplateRenderer().render(
        _template(body="{text} {nonexistent}"),
        title="T",
        text="Body",
        source="S",
    )
    assert "Body" in out


def test_html_format_escapes_dynamic_values() -> None:
    out = TemplateRenderer().render(
        _template(format=TemplateFormat.HTML, header="{title}", body="{text}", footer=""),
        title="<script>",
        text="x & y",
    )
    assert "&lt;script&gt;" in out
    assert "x &amp; y" in out
