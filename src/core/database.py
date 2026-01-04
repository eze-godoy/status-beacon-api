"""Async database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create async database engine with connection pooling.

    Args:
        settings: Application settings containing database configuration.

    Returns:
        Configured async SQLAlchemy engine.
    """
    return create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory.

    Args:
        engine: The async database engine.

    Returns:
        Configured async session maker.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Dependency for getting database sessions.

    Yields:
        Database session that auto-closes on exit.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
