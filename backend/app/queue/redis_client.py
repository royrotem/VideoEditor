"""Async Redis client factory and health check."""

from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import ExternalServiceError


def create_redis_client(settings: Settings) -> Redis:
    """Build an async :class:`Redis` client from settings."""
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=False,
    )


async def redis_health_check(client: Redis) -> None:
    """Ping the Redis server; raise :class:`ExternalServiceError` on failure."""
    try:
        await client.ping()
    except RedisError as exc:
        raise ExternalServiceError(f"redis unreachable: {exc}") from exc
