"""Integration tests for database connectivity.

IMPORTANT: These tests require a running PostgreSQL database.
Start the database with: docker-compose up -d db

These tests use the test_db_session fixture to ensure proper
event loop isolation and avoid "Future attached to different loop" errors.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection(test_db_session: AsyncSession) -> None:
    """Test basic database connectivity using fixture (NOT module import).

    This test verifies that we can connect to the database and execute
    a simple query.

    Args:
        test_db_session: Test database session fixture.
    """
    # Execute a simple query
    result = await test_db_session.execute(text("SELECT 1"))
    value = result.scalar_one()

    assert value == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_session_lifecycle(test_db_session: AsyncSession) -> None:
    """Test database session lifecycle and transaction handling.

    Args:
        test_db_session: Test database session fixture.
    """
    # Verify session is active
    assert test_db_session.is_active

    # Execute a query
    result = await test_db_session.execute(text("SELECT 1 as value"))
    row = result.first()

    assert row is not None
    assert row[0] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_metadata_operations(test_db_session: AsyncSession) -> None:
    """Test database metadata operations.

    Args:
        test_db_session: Test database session fixture.
    """
    # Query database version
    result = await test_db_session.execute(text("SELECT version()"))
    version = result.scalar_one()

    # Verify we're connected to PostgreSQL
    assert "PostgreSQL" in version


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_transaction_rollback(test_db_session: AsyncSession) -> None:
    """Test that transactions can be rolled back properly.

    Args:
        test_db_session: Test database session fixture.
    """
    # Start a transaction by executing a query
    result = await test_db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1

    # Rollback the transaction
    await test_db_session.rollback()

    # Verify we can still use the session
    result = await test_db_session.execute(text("SELECT 2"))
    assert result.scalar_one() == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection_pool(test_db_engine: AsyncEngine) -> None:
    """Test database connection pool behavior.

    Args:
        test_db_engine: Test database engine fixture.
    """
    # Verify engine is configured
    assert test_db_engine is not None

    # Test multiple connections can be acquired
    async with test_db_engine.connect() as conn1:
        result1 = await conn1.execute(text("SELECT 1"))
        assert result1.scalar_one() == 1

    async with test_db_engine.connect() as conn2:
        result2 = await conn2.execute(text("SELECT 2"))
        assert result2.scalar_one() == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection_recovery(test_db_session: AsyncSession) -> None:
    """Test that database connection can recover from errors.

    Args:
        test_db_session: Test database session fixture.
    """
    # Execute a valid query
    result = await test_db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1

    # Execute an invalid query to test error recovery
    # B017: Using bare Exception is intentional here. This test validates connection
    # recovery after ANY database error, not specific error types. SQLAlchemy may raise
    # different exceptions (ProgrammingError, OperationalError) depending on the driver
    # and database version, so we intentionally catch the broad Exception type.
    with pytest.raises(Exception):  # noqa: B017
        await test_db_session.execute(text("SELECT * FROM nonexistent_table"))

    # Rollback to recover
    await test_db_session.rollback()

    # Verify connection still works
    result = await test_db_session.execute(text("SELECT 2"))
    assert result.scalar_one() == 2
