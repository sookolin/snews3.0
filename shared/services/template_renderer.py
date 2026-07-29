"""Template rendering service.

Renders a :class:`~shared.models.template.Template` into the final publication
text. Supports HTML, Markdown and Telegram-HTML formats and safe placeholder
substitution (missing placeholders render as empty strings, never raise).
"""

from __future__ import annotations

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
        author: str = "",
        emoji: str = "",
        published_at: datetime | None = None,
        link: str = "",
    ) -> str:
        """Return the fully rendered publication text.

        ``link`` is the subscribe link resolved for the *city* the post belongs
        to (its Telegram channel). It wins over the template's static
        ``subscribe_link`` so one shared template can be reused by every city
        and still link to the right channel.
        """
        link = link or template.subscribe_link or source_url or ""
        date_str = (published_at or datetime.now()).strftime("%d.%m.%Y %H:%M")

        if getattr(template, "uppercase_title", False) and title:
            title = title.upper()

        custom_emoji = ""
        # {source} becomes a hyperlink to the original publication when a URL is
        # known, so the link lives inside the post itself.
        source_rendered = self._prepare(source, template.format)
        if source_rendered and source_url:
            source_rendered = f'<a href="{source_url}">{source_rendered}</a>'

        variables = _SafeDict(
            title=self._prepare(title, template.format),
            text=self._prepare(text, template.format),
            source=source_rendered,
            source_plain=self._prepare(source, template.format),
            source_url=source_url,
            city=self._prepare(city, template.format),
            author=self._prepare(author, template.format),
            emoji=emoji or "",
            custom_emoji=custom_emoji,
            date=date_str,
            link=link,
            footer="",
        )
        # show_author / show_source toggles stored in custom variables.
        # If the template sets show_author=0 or show_source=0, suppress the value.
        _vars_raw = template.variables or {}
        if str(_vars_raw.get("show_author", "1")) == "0":
            author = ""
        if str(_vars_raw.get("show_source", "1")) == "0":
            source = ""
            source_url = ""
        # Merge custom template variables (already assumed safe / author-provided).
        for key, value in (template.variables or {}).items():
            variables.setdefault(key, str(value))

        parts = [
            template.header.format_map(variables),
            template.body.format_map(variables),
            template.footer.format_map(variables),
        ]
        rendered = template.separator.join(p for p in parts if p.strip())
        rendered = self._drop_empty_label_lines(rendered)
        return rendered.strip()

    @staticmethod
    def _drop_empty_label_lines(text: str) -> str:
        """Remove lines that are just an empty label like 'Источник:' / 'Автор:'.

        Also collapses 'Источник:' style HTML-link labels whose value/link is
        empty. Keeps the rest of the layout intact.
        """
        import re

        # Normalise <br> variants to real newlines first, so label lines can be
        # detected even when a template uses <br> as its separator.
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

        cleaned_lines: list[str] = []
        # A line is dropped if, after stripping HTML tags, it is a label ending
        # with ':' and nothing meaningful after it.
        label_re = re.compile(r"^\s*[^:<>]{1,40}:\s*$")
        for line in text.split("\n"):
            stripped_tags = re.sub(r"<[^>]+>", "", line).strip()
            if label_re.match(stripped_tags):
                continue
            cleaned_lines.append(line)
        result = "\n".join(cleaned_lines)
        return re.sub(r"\n{3,}", "\n\n", result)

    @staticmethod
    def _prepare(value: str, fmt: TemplateFormat) -> str:
        """Prepare a dynamic value for insertion into the template.

        All rendered output is destined for Telegram with ``parse_mode=HTML``,
        and unsafe tags are stripped later by
        :func:`shared.services.html_sanitizer.sanitize_telegram_html`.
        Therefore we must NOT HTML-escape the values here — doing so would turn
        intended markup like ``<b>`` into literal text.
        """
        if value is None:
            return ""
        return value
