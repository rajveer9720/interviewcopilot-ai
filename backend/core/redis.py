"""Redis client with connection pool."""

from redis.asyncio import Redis, ConnectionPool
from backend.config import settings

_pool: ConnectionPool | None = None
redis_client: Redis | None = None


async def init_redis():
    global _pool, redis_client
    _pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_POOL_SIZE,
        decode_responses=True,
    )
    redis_client = Redis(connection_pool=_pool)


async def close_redis():
    if redis_client:
        await redis_client.aclose()
    if _pool:
        await _pool.aclose()


def get_redis() -> Redis:
    """FastAPI dependency."""
    return redis_client
