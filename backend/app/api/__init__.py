"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api import (
    ads,
    ai,
    auth,
    channels,
    cities,
    dashboard,
    media,
    news,
    sources,
    templates,
    users,
    watermarks,
)
from backend.app.api import (
    settings as settings_router,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(cities.router, prefix="/cities", tags=["cities"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(watermarks.router, prefix="/watermarks", tags=["watermarks"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(ads.router, prefix="/ads", tags=["ads"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["settings"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

__all__ = ["api_router"]
