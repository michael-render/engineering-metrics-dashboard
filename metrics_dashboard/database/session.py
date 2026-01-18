"""Database session factory for async SQLAlchemy."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_database_url() -> str:
    """Get database URL from environment.

    Supports both DATABASE_URL (Render format) and individual components.
    Converts postgres:// to postgresql+asyncpg:// for async driver.
    """
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # Render provides postgres:// URLs, convert for asyncpg
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return database_url

    # Fallback to individual components (for local development)
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    database = os.environ.get("DB_NAME", "engineering_metrics")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


# Create async engine (lazy initialization)
_engine = None
_session_factory = None


def _get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            echo=os.environ.get("DB_ECHO", "").lower() == "true",
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    Usage:
        async with get_async_session() as session:
            # Use session
            await session.execute(...)
            await session.commit()
    """
    session = _get_session_factory()()
    try:
        yield session
    finally:
        await session.close()


async def get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session_dependency)):
            ...
    """
    async with get_async_session() as session:
        yield session
