"""
FastAPI application factory.
Registers all routers, middleware, and startup/shutdown events.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config import settings
from backend.core.database import engine, Base
from backend.core.redis import init_redis, close_redis
from backend.core.middleware import RateLimitMiddleware, RequestLoggingMiddleware

from backend.auth.router import router as auth_router
from backend.sessions.router import router as sessions_router
from backend.sessions.ws_handler import router as ws_router
from backend.resume.router import router as resume_router
from backend.feedback.router import router as feedback_router
from backend.billing.router import router as billing_router
from backend.analytics.router import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    await init_redis()
    # In dev, auto-create tables. In prod, use Alembic migrations.
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── REST Routers ───────────────────────────────
    PREFIX = "/api/v1"
    app.include_router(auth_router,      prefix=f"{PREFIX}/auth",      tags=["auth"])
    app.include_router(sessions_router,  prefix=f"{PREFIX}/sessions",  tags=["sessions"])
    app.include_router(resume_router,    prefix=f"{PREFIX}/resumes",   tags=["resumes"])
    app.include_router(feedback_router,  prefix=f"{PREFIX}/feedback",  tags=["feedback"])
    app.include_router(billing_router,   prefix=f"{PREFIX}/billing",   tags=["billing"])
    app.include_router(analytics_router, prefix=f"{PREFIX}/analytics", tags=["analytics"])

    # ── WebSocket Routers ──────────────────────────
    app.include_router(ws_router, tags=["websocket"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()
