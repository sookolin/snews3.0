"""API integration tests (SQLite-backed, auth overridden)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_me(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.example"


async def test_city_crud_flow(client: AsyncClient) -> None:
    # Create
    resp = await client.post(
        "/api/v1/cities",
        json={"name": "Казань", "keywords": ["казань", "татарстан"], "language": "ru"},
    )
    assert resp.status_code == 201, resp.text
    city = resp.json()
    assert city["slug"] == "kazan"
    city_id = city["id"]

    # List
    resp = await client.get("/api/v1/cities")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Update
    resp = await client.patch(f"/api/v1/cities/{city_id}", json={"description": "столица РТ"})
    assert resp.status_code == 200
    assert resp.json()["description"] == "столица РТ"

    # Delete
    resp = await client.delete(f"/api/v1/cities/{city_id}")
    assert resp.status_code == 200


async def test_template_crud_and_preview(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/templates",
        json={"name": "Main", "is_default": True, "header": "🔥 {title}", "body": "{text}"},
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/templates/{template_id}/preview")
    assert resp.status_code == 200
    assert "🔥" in resp.json()["detail"]


async def test_news_listing_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
