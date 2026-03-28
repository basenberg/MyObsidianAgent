"""Custom exception classes and global exception handlers."""

from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# Custom exception classes
class DatabaseError(Exception):
    """Base exception for database-related errors."""

    pass


class NotFoundError(DatabaseError):
    """Exception raised when a resource is not found."""

    pass


class ValidationError(DatabaseError):
    """Exception raised when validation fails."""

    pass


# Global exception handlers
async def database_exception_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle database exceptions globally.

    Args:
        request: The incoming request.
        exc: The database exception that was raised.

    Returns:
        JSONResponse with error details.
    """
    logger.error(
        "database.error",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, NotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    return JSONResponse(
        status_code=status_code,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    # FastAPI's type system expects exception handlers with exact type signatures
    # matching each exception class. However, our database_exception_handler uses
    # polymorphism to handle DatabaseError and all its subtypes (NotFoundError,
    # ValidationError) with a single implementation. This is a valid design pattern
    # that reduces code duplication. We use cast(Any, ...) to inform the type checker
    # that we're intentionally using polymorphic exception handling.
    handler: Any = cast(Any, database_exception_handler)

    app.add_exception_handler(DatabaseError, handler)
    app.add_exception_handler(NotFoundError, handler)
    app.add_exception_handler(ValidationError, handler)
