"""
Shared pytest fixtures.

Tests run against an in-memory SQLite DB (via `aiosqlite`) and a fake Redis
(via `fakeredis`) — zero external Postgres/Redis needed. The app's real
`lifespan` (which connects to the real Redis/DATABASE_URL from `.env`) is
deliberately never triggered here: `httpx.ASGITransport` doesn't invoke it,
and these fixtures substitute the pieces it would have set up.
"""

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

import backend.core.redis as redis_module
from backend.core.database import Base, get_db
from backend.main import app


# Models use Postgres-only `JSONB` columns (see resume/sessions/feedback
# models.py); the SQLite test DB has no native equivalent to compile it
# against. This registers a SQLite rendering (as JSON) so
# `Base.metadata.create_all` works against the in-memory test engine — the
# production DB always speaks real Postgres, this only affects tests.
@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json_on_sqlite(element, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_module.redis_client = client
    yield client
    await client.aclose()
    redis_module.redis_client = None


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, fake_redis) -> AsyncIterator[AsyncClient]:
    """An HTTP client wired to the real FastAPI app, with DB/Redis swapped
    for the isolated test doubles above."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
