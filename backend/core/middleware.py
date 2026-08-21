"""
Middleware: rate limiting (Redis sliding window) + request logging.
"""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.config import settings
from backend.core import redis as redis_service

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis.
    Limits are applied per IP + endpoint category.
    """

    LIMITS = {
        "/api/v1/auth":     settings.RATE_LIMIT_AUTH_PER_MINUTE,
        "/api/v1":          settings.RATE_LIMIT_API_PER_MINUTE,
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        ip = request.client.host
        path = request.url.path

        limit = self._get_limit(path)
        if limit and redis_service.redis_client:
            key = f"rl:{ip}:{path.split('/')[3] if len(path.split('/')) > 3 else 'api'}"
            try:
                current = await redis_service.redis_client.incr(key)
                if current == 1:
                    await redis_service.redis_client.expire(key, 60)
                if current > limit:
                    return Response(
                        content='{\"detail\": \"Rate limit exceeded. Please slow down.\"}',
                        status_code=429,
                        media_type="application/json",
                    )
            except Exception:
                logger.warning("Redis rate limiting unavailable", exc_info=True)

        response = await call_next(request)
        return response

    def _get_limit(self, path: str) -> int | None:
        if path.startswith("/api/v1/auth"):
            return self.LIMITS["/api/v1/auth"]
        if path.startswith("/api/v1"):
            return self.LIMITS["/api/v1"]
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status, and duration for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            "%s %s → %d  (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response
