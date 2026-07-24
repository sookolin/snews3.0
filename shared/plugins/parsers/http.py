"""Shared HTTP helpers for parsers (proxy, headers, cookies, auth, timeout)."""

from __future__ import annotations

from typing import Any

import httpx

from shared.models.source import Source


def build_client(source: Source) -> httpx.AsyncClient:
    """Construct an ``httpx.AsyncClient`` configured from a source."""
    headers: dict[str, str] = {
        "User-Agent": ("Mozilla/5.0 (compatible; CityNewsBot/3.0; +https://example.com/bot)"),
    }
    headers.update({str(k): str(v) for k, v in (source.headers or {}).items()})

    cookies = {str(k): str(v) for k, v in (source.cookies or {}).items()}

    auth: httpx.Auth | None = None
    auth_cfg: dict[str, Any] = source.auth or {}
    if auth_cfg.get("type") == "basic" and auth_cfg.get("username"):
        auth = httpx.BasicAuth(auth_cfg["username"], auth_cfg.get("password", ""))
    elif auth_cfg.get("type") == "bearer" and auth_cfg.get("token"):
        headers["Authorization"] = f"Bearer {auth_cfg['token']}"

    proxy = source.proxy_url if source.use_proxy and source.proxy_url else None

    return httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        auth=auth,
        proxy=proxy,
        timeout=httpx.Timeout(source.timeout_seconds),
        follow_redirects=True,
    )
