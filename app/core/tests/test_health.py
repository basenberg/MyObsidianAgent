"""Unit tests for health check endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from app.core.health import database_health_check, health_check, readiness_check


@pytest.mark.asyncio
async def test_health_check_returns_healthy():
    """Test that basic health check returns healthy status."""
    response = await health_check()

    assert response["status"] == "healthy"
    assert response["service"] == "api"


@pytest.mark.asyncio
async def test_database_health_check_success():
    """Test database health check with successful connection."""
    # Create a mock database session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    response = await database_health_check(db=mock_db)

    # Verify database was queried
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == "SELECT 1"

    # Verify response
    assert response["status"] == "healthy"
    assert response["service"] == "database"
    assert response["provider"] == "postgresql"


@pytest.mark.asyncio
async def test_database_health_check_failure():
    """Test database health check with failed connection."""
    # Create a mock database session that raises an exception
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Database connection failed"))

    # Patch the logger to avoid log output in tests
    with patch("app.core.health.logger.error"):
        with pytest.raises(HTTPException) as exc_info:
            await database_health_check(db=mock_db)

    # Verify the exception
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Database is not accessible" in exc_info.value.detail


@pytest.mark.asyncio
async def test_readiness_check_success():
    """Test readiness check with all dependencies healthy."""
    # Create a mock database session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    # Patch get_settings to return test settings
    with patch("app.core.health.get_settings") as mock_get_settings:
        mock_settings = AsyncMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        response = await readiness_check(db=mock_db)

    # Verify database was queried
    mock_db.execute.assert_called_once()

    # Verify response
    assert response["status"] == "ready"
    assert response["environment"] == "test"
    assert response["database"] == "connected"


@pytest.mark.asyncio
async def test_readiness_check_failure():
    """Test readiness check with failed dependencies."""
    # Create a mock database session that fails
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Database not ready"))

    # Patch get_settings
    with patch("app.core.health.get_settings") as mock_get_settings:
        mock_settings = AsyncMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        # Patch the logger
        with patch("app.core.health.logger.error"):
            with pytest.raises(HTTPException) as exc_info:
                await readiness_check(db=mock_db)

    # Verify the exception
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Application is not ready" in exc_info.value.detail


@pytest.mark.asyncio
async def test_database_health_check_logs_error():
    """Test that database health check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection error"))

    with patch("app.core.health.logger.error") as mock_logger:
        with pytest.raises(HTTPException):
            await database_health_check(db=mock_db)

        # Verify logger was called with exc_info=True
        mock_logger.assert_called_once()
        assert "database.health_check_failed" in str(mock_logger.call_args)


@pytest.mark.asyncio
async def test_readiness_check_logs_error():
    """Test that readiness check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Not ready"))

    with patch("app.core.health.get_settings"):
        with patch("app.core.health.logger.error") as mock_logger:
            with pytest.raises(HTTPException):
                await readiness_check(db=mock_db)

            # Verify logger was called with exc_info=True
            mock_logger.assert_called_once()
            assert "health.readiness_check_failed" in str(mock_logger.call_args)
