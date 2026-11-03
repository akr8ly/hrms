"""Shared Redis client for security-sensitive ephemeral application state."""

from functools import lru_cache

import redis
from redis.exceptions import RedisError


class SecurityStateUnavailable(RuntimeError):
    """Raised when Redis cannot safely serve security state."""


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    # Imported lazily to avoid a configuration import cycle.
    from app.security import auth_settings

    return redis.Redis.from_url(
        auth_settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=auth_settings.redis_connect_timeout_seconds,
        socket_timeout=auth_settings.redis_operation_timeout_seconds,
        health_check_interval=30,
    )


def require_redis(operation):
    """Translate Redis driver failures into a safe application error."""
    try:
        return operation()
    except RedisError as error:
        raise SecurityStateUnavailable(
            "Security state is temporarily unavailable"
        ) from error