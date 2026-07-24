"""Async Redis client helper (shared connection pool)."""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.config import settings

_pool: aioredis.ConnectionPool | None = None


def get_redis() -> aioredis.Redis:
    """Return a Redis client backed by a shared connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis() -> None:
    """Dispose the shared connection pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
