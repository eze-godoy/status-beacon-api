"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing app
# This ensures tests don't accidentally use production config
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("ENVIRONMENT", "development")

from src.api.dependencies import get_db_session
from src.main import app
from src.models import Base, Service

# Use in-memory SQLite for unit tests (fast, no external deps)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    """Create a test database session with automatic rollback."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Create an async test client with mocked database session."""

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def service_factory(db_session: AsyncSession):
    """Factory for creating test services."""

    async def create_service(**kwargs) -> Service:
        defaults = {
            "name": f"Test Service {uuid4().hex[:8]}",
            "provider": "test",
            "status_url": "https://example.com/status",
            "is_active": True,
        }
        defaults.update(kwargs)
        service = Service(**defaults)
        db_session.add(service)
        await db_session.flush()
        return service

    return create_service
