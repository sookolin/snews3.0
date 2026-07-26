"""Sanitize arbitrary HTML into the subset Telegram accepts.

Telegram's HTML parse mode only allows: b, strong, i, em, u, ins, s, strike,
del, span (only with class="tg-spoiler"), tg-spoiler, a, code, pre, blockquote.
Any other tag (div, span, p, br, h1..h6, ul/li, img, font, etc.) causes a
"can't parse entities" API error. This module strips/normalises unsupported
tags while preserving text and line breaks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_ALLOWED = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "a", "code", "pre", "blockquote", "tg-spoiler",
}
# Tags that should become a newline when opened/closed.
_BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}


class _TelegramHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # Stack of booleans: True if the span was emitted as a spoiler span.
        self._span_stack: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = dict(attrs)
        if tag == "span":
            is_spoiler = (attr.get("class") or "").strip() == "tg-spoiler"
            self._span_stack.append(is_spoiler)
            if is_spoiler:
                self.out.append('<span class="tg-spoiler">')
            return
        if tag == "a":
            href = attr.get("href") or ""
            if href:
                self.out.append(f'<a href="{_escape_attr(href)}">')
            return
        if tag in _ALLOWED:
            self.out.append(f"<{tag}>")
        elif tag in _BLOCK:
            if tag != "br":
                pass
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "span":
            was_spoiler = self._span_stack.pop() if self._span_stack else False
            if was_spoiler:
                self.out.append("</span>")
            return
        if tag in _ALLOWED:
            self.out.append(f"</{tag}>")
        elif tag in _BLOCK and tag != "br":
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        self.out.append(
            data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def get_output(self) -> str:
        text = "".join(self.out)
        # Collapse 3+ newlines to 2, trim.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def sanitize_telegram_html(html: str) -> str:
    """Return ``html`` reduced to Telegram-safe HTML."""
    if not html:
        return ""
    parser = _TelegramHTMLSanitizer()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - never fail publishing over sanitisation
        # Fallback: strip all tags.
        return re.sub(r"<[^>]+>", "", html).strip()
    return parser.get_output()
