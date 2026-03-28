"""Request/response middleware for FastAPI application.

This module provides:
- Request logging middleware with correlation IDs
- Request ID extraction from headers or generation
- Request/response lifecycle logging
- CORS middleware setup
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, get_request_id, set_request_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with correlation ID.

    This middleware:
    1. Extracts or generates a request ID for each request
    2. Sets the request ID in context for correlation across logs
    3. Logs request.http_received with method, path, and client info
    4. Logs request.http_completed with status code and duration
    5. Logs request.http_failed with full exception info on errors
    6. Adds X-Request-ID to response headers
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process each request and response.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response with X-Request-ID header added.

        Raises:
            Exception: Re-raises any exception after logging it.
        """
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        set_request_id(request_id)

        start_time = time.time()
        logger.info(
            "request.http_received",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                "request.http_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,  # pyright: ignore[reportUnknownMemberType]
                duration_seconds=round(duration, 3),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = get_request_id()  # pyright: ignore[reportUnknownMemberType]
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request.http_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_seconds=round(duration, 3),
                exc_info=True,
            )
            raise


def setup_middleware(app: FastAPI) -> None:
    """Set up all middleware for the application.

    Adds:
    1. RequestLoggingMiddleware for request/response logging
    2. CORSMiddleware for cross-origin requests

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
