"""Async engine + session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Base

log = get_logger(__name__)

_connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    # SQLite + async: keep the default single connection honest across the loop.
    _connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create the schema (and the pgvector extension when on Postgres).

    Alembic is the production path; this keeps first-run friction at zero.
    """
    async with engine.begin() as conn:
        if settings.is_postgres:
            from sqlalchemy import text

            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    log.info("db_ready", dialect=engine.dialect.name)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. One transaction per request."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
