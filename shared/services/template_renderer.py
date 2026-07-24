"""Template rendering service.

Renders a :class:`~shared.models.template.Template` into the final publication
text. Supports HTML, Markdown and Telegram-HTML formats and safe placeholder
substitution (missing placeholders render as empty strings, never raise).
"""

from __future__ import annotations

import html
from datetime import datetime

from shared.enums import TemplateFormat
from shared.models.template import Template


class _SafeDict(dict):
    """A dict that returns an empty string for missing keys in ``format_map``."""

    def __missing__(self, key: str) -> str:
        return ""


class TemplateRenderer:
    """Render templates with variable substitution and format-aware escaping."""

    def render(
        self,
        template: Template,
        *,
        title: str,
        text: str,
        source: str = "",
        source_url: str = "",
        city: str = "",
        published_at: datetime | None = None,
    ) -> str:
        """Return the fully rendered publication text."""
        link = template.subscribe_link or source_url or ""
        date_str = (published_at or datetime.now()).strftime("%d.%m.%Y %H:%M")

        variables = _SafeDict(
            title=self._prepare(title, template.format),
            text=self._prepare(text, template.format),
            source=self._prepare(source, template.format),
            source_url=source_url,
            city=self._prepare(city, template.format),
            date=date_str,
            link=link,
            footer="",
        )
        # Merge custom template variables (already assumed safe / author-provided).
        for key, value in (template.variables or {}).items():
            variables.setdefault(key, str(value))

        parts = [
            template.header.format_map(variables),
            template.body.format_map(variables),
            template.footer.format_map(variables),
        ]
        rendered = template.separator.join(p for p in parts if p.strip())
        return rendered.strip()

    @staticmethod
    def _prepare(value: str, fmt: TemplateFormat) -> str:
        """Escape a raw dynamic value according to the template format.

        The AI output may already contain intended HTML tags for Telegram, so
        for the Telegram-HTML format we do *not* escape (the AI is instructed to
        emit only safe tags). For plain HTML we escape to avoid injection.
        """
        if value is None:
            return ""
        if fmt == TemplateFormat.HTML:
            return html.escape(value)
        return value
