"""Alembic environment for async SQLAlchemy (asyncpg)."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Import all models so Alembic can detect schema changes ──────────────────
# NOTE: these use the same `backend.` package-qualified imports as the rest of
# the app. Alembic must therefore be invoked with the repository root (the
# parent of this `backend/` package) on sys.path — see `prepend_sys_path`
# below, which adds it relative to the working directory Alembic is run from
# (the `backend/` directory, per convention: `cd backend && alembic ...`).
from backend.core.database import Base  # noqa: F401
from backend.config import settings
import backend.auth.models  # noqa: F401
import backend.sessions.models  # noqa: F401
import backend.resume.models  # noqa: F401
import backend.feedback.models  # noqa: F401
import backend.billing.models  # noqa: F401

config = context.config

# Override sqlalchemy.url from environment variable
database_url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
# asyncpg requires the driver prefix
if database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", database_url or "")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
