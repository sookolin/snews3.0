"""Tests for the Telegram HTML sanitizer (tag filtering + balance)."""

from __future__ import annotations

import re

from shared.services.html_sanitizer import sanitize_telegram_html as sanitize


def _balanced(html: str) -> bool:
    """Verify every opened tag is closed in the right order."""
    stack: list[str] = []
    for match in re.finditer(r"<(/?)([a-z-]+)[^>]*>", html):
        closing, tag = match.group(1), match.group(2)
        if closing:
            if not stack or stack.pop() != tag:
                return False
        else:
            stack.append(tag)
    return not stack


def test_stray_closing_tag_removed() -> None:
    out = sanitize("text</b> more")
    assert "</b>" not in out
    assert _balanced(out)


def test_unclosed_tag_is_closed() -> None:
    out = sanitize("<b>bold never closed")
    assert out == "<b>bold never closed</b>"
    assert _balanced(out)


def test_bad_nesting_is_corrected() -> None:
    out = sanitize("<b><i>x</b></i>")
    assert _balanced(out)
    assert "x" in out


def test_unsupported_tags_stripped_but_text_kept() -> None:
    out = sanitize("<div>line1</div><div>line2</div>")
    assert "div" not in out
    assert "line1" in out and "line2" in out


def test_spoiler_span_preserved_plain_span_unwrapped() -> None:
    assert 'class="tg-spoiler"' in sanitize('<span class="tg-spoiler">s</span>')
    assert sanitize("<span>plain</span>") == "plain"


def test_tg_emoji_preserved() -> None:
    out = sanitize('<tg-emoji emoji-id="123">X</tg-emoji>')
    assert 'emoji-id="123"' in out
    assert _balanced(out)


def test_script_is_removed() -> None:
    out = sanitize("<script>bad()</script>ok")
    assert "script" not in out
    assert "ok" in out
