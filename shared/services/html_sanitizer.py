"""Sanitize arbitrary HTML into the subset Telegram accepts.

Telegram's HTML parse mode only allows: b, strong, i, em, u, ins, s, strike,
del, span (only with class="tg-spoiler"), tg-spoiler, a, code, pre, blockquote,
tg-emoji. Any other tag (div, p, br, h1..h6, ul/li, img, font, …) causes a
"can't parse entities" API error.

Beyond filtering tags, this module guarantees the output is **well balanced**:
stray closing tags are dropped and unclosed tags are closed at the end. Telegram
rejects unbalanced markup with "Unexpected end tag", so this is essential.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

#: Inline tags Telegram accepts as-is.
_ALLOWED = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "a", "code", "pre", "blockquote", "tg-spoiler",
}
#: Tags that carry no meaning for Telegram but imply a line break.
_BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "ul", "ol"}
#: Tags that never have content (must not go on the stack).
_VOID = {"br", "img", "hr", "input", "meta", "link"}


class _TelegramHTMLSanitizer(HTMLParser):
    """Filter tags to the Telegram subset and keep the markup balanced."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        #: Stack of emitted tag names awaiting a closing tag.
        self._stack: list[str] = []

    # ── opening tags ────────────────────────────────────────────────────────
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = dict(attrs)

        if tag in _VOID:
            if tag == "br":
                self.out.append("\n")
            return

        if tag == "span":
            # Only class="tg-spoiler" spans are valid; others are unwrapped.
            if (attr.get("class") or "").strip() == "tg-spoiler":
                self.out.append('<span class="tg-spoiler">')
                self._stack.append("span")
            else:
                self._stack.append("")  # placeholder: emitted nothing
            return

        if tag == "tg-emoji":
            emoji_id = attr.get("emoji-id") or ""
            if emoji_id:
                self.out.append(f'<tg-emoji emoji-id="{_escape_attr(emoji_id)}">')
                self._stack.append("tg-emoji")
            else:
                self._stack.append("")
            return

        if tag == "a":
            href = attr.get("href") or ""
            if href:
                self.out.append(f'<a href="{_escape_attr(href)}">')
                self._stack.append("a")
            else:
                self._stack.append("")
            return

        if tag in _ALLOWED:
            self.out.append(f"<{tag}>")
            self._stack.append(tag)
            return

        if tag in _BLOCK:
            self.out.append("\n")
            self._stack.append("")  # keep nesting aligned, emit nothing
            return

        # Unknown tag: drop it but remember the nesting level.
        self._stack.append("")

    # ── closing tags ────────────────────────────────────────────────────────
    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _VOID:
            return

        if not self._stack:
            # Stray closing tag with no opener — drop it entirely.
            return

        # Find the matching opener, closing anything opened after it.
        expected = "span" if tag == "span" else tag
        target_index = None
        for i in range(len(self._stack) - 1, -1, -1):
            entry = self._stack[i]
            if entry == expected or (entry == "" and expected not in self._stack):
                target_index = i
                break
        if target_index is None:
            # No matching opener anywhere: drop the stray closing tag.
            return

        # Close tags above the target (inner-first) to keep nesting valid.
        while len(self._stack) - 1 > target_index:
            inner = self._stack.pop()
            if inner:
                self.out.append(f"</{inner}>")

        entry = self._stack.pop()
        if entry:
            self.out.append(f"</{entry}>")
        elif tag in _BLOCK:
            self.out.append("\n")

    # ── text ────────────────────────────────────────────────────────────────
    def handle_data(self, data: str) -> None:
        self.out.append(
            data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def get_output(self) -> str:
        # Close anything still open so Telegram never sees dangling tags.
        while self._stack:
            entry = self._stack.pop()
            if entry:
                self.out.append(f"</{entry}>")
        text = "".join(self.out)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def sanitize_telegram_html(html: str) -> str:
    """Return ``html`` reduced to well-balanced, Telegram-safe HTML."""
    if not html:
        return ""
    parser = _TelegramHTMLSanitizer()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - never fail publishing over sanitisation
        return re.sub(r"<[^>]+>", "", html).strip()
    return parser.get_output()
