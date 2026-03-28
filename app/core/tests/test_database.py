"""Unit tests for database configuration and session management."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.database import Base, get_db


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """Test that get_db yields an AsyncSession and closes it properly."""
    # Mock the AsyncSessionLocal to avoid actual database connection
    with patch("app.core.database.AsyncSessionLocal") as mock_session_factory:
        # Create a mock session with proper async context manager
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.close = AsyncMock()

        # Configure the factory to return our mock
        mock_session_factory.return_value = mock_session

        # Use the get_db generator
        async for session in get_db():
            # Verify we got a session
            assert session is not None
            # Verify the session is accessible
            assert session == mock_session

        # Verify close was called
        mock_session.close.assert_called_once()


def test_base_class_is_declarative_base():
    """Test that Base is properly configured as a DeclarativeBase."""
    # Verify Base is a class
    assert isinstance(Base, type)

    # Verify Base has metadata attribute (characteristic of DeclarativeBase)
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


@pytest.mark.asyncio
async def test_engine_configuration():
    """Test that the async engine is properly configured."""
    from app.core.database import engine

    # Verify engine is an AsyncEngine
    assert isinstance(engine, AsyncEngine)

    # Verify engine URL contains asyncpg driver
    assert "asyncpg" in str(engine.url)
