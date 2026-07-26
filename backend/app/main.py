"""FastAPI application factory, middleware and exception handling."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api import api_router
from shared.config import settings
from shared.exceptions import AppError
from shared.logging import configure_logging, get_logger
from shared.redis_client import close_redis

log = get_logger("backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: configure logging, load plugins, cleanup."""
    configure_logging()
    # Import triggers plugin registration.
    import shared.plugins  # noqa: F401

    log.info("backend_startup", env=settings.app_env)
    yield
    await close_redis()
    log.info("backend_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="3.0.0",
        description="City news monitoring, AI processing and Telegram publishing platform.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Serve uploaded media directly (dev + as a fallback behind nginx).
    import os

    from fastapi.staticfiles import StaticFiles

    os.makedirs(settings.media_root, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    return app


app = create_app()
