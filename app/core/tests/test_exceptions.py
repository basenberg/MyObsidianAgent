"""Unit tests for custom exceptions and exception handlers."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    DatabaseError,
    NotFoundError,
    ValidationError,
    database_exception_handler,
    setup_exception_handlers,
)


def test_database_error_is_exception():
    """Test that DatabaseError is properly defined and can be raised."""
    with pytest.raises(DatabaseError):
        raise DatabaseError("Test error")


def test_not_found_error_inherits_from_database_error():
    """Test that NotFoundError inherits from DatabaseError."""
    assert issubclass(NotFoundError, DatabaseError)

    with pytest.raises(NotFoundError):
        raise NotFoundError("Resource not found")

    # Verify it can also be caught as DatabaseError
    with pytest.raises(DatabaseError):
        raise NotFoundError("Resource not found")


def test_validation_error_inherits_from_database_error():
    """Test that ValidationError inherits from DatabaseError."""
    assert issubclass(ValidationError, DatabaseError)

    with pytest.raises(ValidationError):
        raise ValidationError("Validation failed")

    # Verify it can also be caught as DatabaseError
    with pytest.raises(DatabaseError):
        raise ValidationError("Validation failed")


@pytest.mark.asyncio
async def test_database_exception_handler_logs_and_returns_json():
    """Test that the exception handler logs errors and returns proper JSON."""
    # Create a mock request
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    # Create an exception
    exc = DatabaseError("Test database error")

    # Patch the logger to verify it's called
    with patch("app.core.exceptions.logger.error") as mock_logger:
        # Call the handler
        response = await database_exception_handler(mock_request, exc)

        # Verify logger was called with exc_info=True
        mock_logger.assert_called_once()
        call_kwargs = mock_logger.call_args[1]
        assert call_kwargs["exc_info"] is True
        assert "error_type" in call_kwargs["extra"]
        assert "error_message" in call_kwargs["extra"]

    # Verify response
    assert isinstance(response, JSONResponse)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.body is not None


@pytest.mark.asyncio
async def test_database_exception_handler_returns_404_for_not_found():
    """Test that NotFoundError returns 404 status code."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    exc = NotFoundError("Resource not found")

    with patch("app.core.exceptions.logger.error"):
        response = await database_exception_handler(mock_request, exc)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_database_exception_handler_returns_422_for_validation():
    """Test that ValidationError returns 422 status code."""
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.method = "GET"

    exc = ValidationError("Validation failed")

    with patch("app.core.exceptions.logger.error"):
        response = await database_exception_handler(mock_request, exc)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_setup_exception_handlers_registers_handlers():
    """Test that setup_exception_handlers registers all exception handlers."""
    # Create a mock FastAPI app
    mock_app = MagicMock()

    # Call setup function
    setup_exception_handlers(mock_app)

    # Verify add_exception_handler was called for each exception type
    assert mock_app.add_exception_handler.call_count == 3

    # Verify the exception types that were registered
    call_args_list = [call[0][0] for call in mock_app.add_exception_handler.call_args_list]
    assert DatabaseError in call_args_list
    assert NotFoundError in call_args_list
    assert ValidationError in call_args_list
