"""FastAPI dependencies for dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Get database session from app state.

    This is a FastAPI dependency that provides a database session
    to route handlers. The session is automatically cleaned up
    when the request completes.

    Args:
        request: The incoming FastAPI request.

    Yields:
        Database session for the request.
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Type alias for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
