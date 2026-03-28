"""Pytest fixtures for integration tests.

IMPORTANT: Integration tests MUST use these fixtures instead of
importing AsyncSessionLocal/engine from app.core.database directly.

Why? The module-level engine in database.py is bound to the first
event loop. pytest-asyncio creates new loops per test. Using fixtures
ensures each test gets an engine bound to its own loop, avoiding
"Future attached to different loop" errors.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@pytest.fixture(scope="function")
async def test_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create fresh database engine for each test.

    This fixture ensures each test gets its own engine bound to the
    test's event loop, preventing event loop conflicts.

    Yields:
        AsyncEngine: Database engine for the test.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,  # Quiet in tests
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(
    test_db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create fresh database session for each test.

    This fixture provides an isolated database session for testing,
    ensuring each test starts with a clean session state.

    Args:
        test_db_engine: The test database engine fixture.

    Yields:
        AsyncSession: Database session for the test.
    """
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with async_session() as session:
        yield session
