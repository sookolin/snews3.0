"""Website/HTML parser supporting BeautifulSoup, lxml and Playwright engines.

Selectors are configured per-source via ``source.selectors``::

    {
      "item": "article.news-card",       # container selector (list mode)
      "title": "h2",                      # relative to item
      "text": ".summary",
      "link": "a@href",                   # @attr extracts an attribute
      "image": "img@src"
    }

If ``item`` is omitted the whole page is treated as a single article.
"""

from __future__ import annotations

from urllib.parse import urljoin

from shared.enums import MediaType, ParserEngine, SourceType
from shared.exceptions import ParserError
from shared.logging import get_logger
from shared.plugins.parsers.base import (
    BaseParser,
    ParsedItem,
    ParsedMedia,
    parser_registry,
)
from shared.plugins.parsers.http import build_client

log = get_logger("parser.website")


class _WebsiteBase(BaseParser):
    """Shared HTML parsing logic for website/html sources."""

    async def _get_html(self) -> str:
        engine = self.source.parser_engine
        if engine == ParserEngine.PLAYWRIGHT:
            return await self._get_html_playwright()
        # AUTO / BEAUTIFULSOUP / LXML all use httpx to fetch raw HTML.
        async with build_client(self.source) as client:
            try:
                response = await client.get(self.source.url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                # AUTO falls back to Playwright for JS-heavy sites on failure.
                if engine == ParserEngine.AUTO:
                    log.warning("website_http_failed_fallback_playwright", error=str(exc))
                    return await self._get_html_playwright()
                raise ParserError(f"Failed to fetch page: {exc}") from exc
            return response.text

    async def _get_html_playwright(self) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise ParserError("Playwright is not installed") from exc

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context_kwargs: dict = {}
                if self.source.use_proxy and self.source.proxy_url:
                    context_kwargs["proxy"] = {"server": self.source.proxy_url}
                context = await browser.new_context(**context_kwargs)
                if self.source.headers:
                    await context.set_extra_http_headers(
                        {str(k): str(v) for k, v in self.source.headers.items()}
                    )
                page = await context.new_page()
                await page.goto(
                    self.source.url,
                    timeout=self.source.timeout_seconds * 1000,
                    wait_until="networkidle",
                )
                html = await page.content()
                await browser.close()
                return html
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"Playwright failed: {exc}") from exc

    def _parse(self, html: str) -> list[ParsedItem]:
        from bs4 import BeautifulSoup

        parser_backend = "lxml" if self.source.parser_engine == ParserEngine.LXML else "html.parser"
        # lxml is preferred when available for speed/robustness.
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:  # noqa: BLE001
            soup = BeautifulSoup(html, parser_backend)

        selectors = self.source.selectors or {}
        item_selector = selectors.get("item")
        base_url = self.source.url

        if not item_selector:
            # Single-article mode: heuristics.
            title = self._extract(soup, selectors.get("title", "h1"))
            text = self._extract(soup, selectors.get("text", "article, .content, main, p"))
            if not text:
                text = soup.get_text(" ", strip=True)[:5000]
            return [
                ParsedItem(
                    title=title,
                    text=text,
                    url=base_url,
                    guid=base_url,
                )
            ]

        items: list[ParsedItem] = []
        for node in soup.select(item_selector):
            title = self._extract(node, selectors.get("title"))
            text = self._extract(node, selectors.get("text")) or title or ""
            link = self._extract_attr(node, selectors.get("link"), base_url)
            image = self._extract_attr(node, selectors.get("image"), base_url)
            if not text:
                continue
            media = [ParsedMedia(type=MediaType.PHOTO, url=image)] if image else []
            items.append(
                ParsedItem(
                    title=title,
                    text=text,
                    url=link,
                    guid=link or (title or "") + text[:64],
                    media=media,
                )
            )
        return items

    @staticmethod
    def _extract(node: object, selector: str | None) -> str | None:
        if not selector:
            return None
        found = node.select_one(selector.split("@")[0])  # type: ignore[attr-defined]
        return found.get_text(" ", strip=True) if found else None

    @staticmethod
    def _extract_attr(node: object, selector: str | None, base_url: str) -> str | None:
        if not selector:
            return None
        css, _, attr = selector.partition("@")
        found = node.select_one(css) if css else node  # type: ignore[attr-defined]
        if not found:
            return None
        if attr:
            value = found.get(attr)
            return urljoin(base_url, value) if value else None
        return found.get_text(" ", strip=True)

    async def fetch(self) -> list[ParsedItem]:
        html = await self._get_html()
        items = self._parse(html)
        log.debug("website_fetched", source=self.source.id, count=len(items))
        return items


@parser_registry.register(SourceType.WEBSITE.value)
class WebsiteParser(_WebsiteBase):
    source_type = SourceType.WEBSITE.value


@parser_registry.register(SourceType.HTML.value)
class HTMLParser(_WebsiteBase):
    source_type = SourceType.HTML.value
