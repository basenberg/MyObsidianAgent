"""Structured logging configuration for the application.

This module provides centralized logging setup with:
- JSON output for AI-parseable logs
- Request ID correlation using context variables
- Hybrid dotted namespace pattern (domain.component.action_state)
- Exception formatting with exc_info for stack traces

Event Naming Pattern:
    Format: {domain}.{component}.{action}_{state}

    Examples:
        - application.lifecycle.started
        - request.http_received
        - database.connection_initialized
        - agent.tool.execution_started

    See docs/logging-standard.md for complete taxonomy.
"""

import logging
import uuid
from contextvars import ContextVar

import structlog
from structlog.typing import EventDict, WrappedLogger

# Context variable for request correlation ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context.

    Returns:
        The current request ID, or empty string if not set.
    """
    return request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set request ID in context, generating one if not provided.

    Args:
        request_id: Optional request ID to set. If None, generates a new UUID.

    Returns:
        The request ID that was set.
    """
    if not request_id:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def add_request_id(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """Processor to add request ID to all log entries.

    Args:
        _logger: The logger instance (unused, required by structlog).
        _method_name: The logging method name (unused, required by structlog).
        event_dict: The event dictionary to process.

    Returns:
        The modified event dictionary with request_id added.
    """
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Sets up structlog with JSON output and the following processors:
    - Request ID correlation
    - Context variables merging
    - Log level addition
    - ISO timestamp
    - Stack info rendering
    - Exception formatting with full tracebacks
    - JSON rendering for AI-parseable output

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    # Convert string log level to integer using logging constants
    # logging.getLevelName(str) is deprecated in Python 3.12+
    level_int = getattr(logging, log_level.upper())

    structlog.configure(
        processors=[
            add_request_id,  # Add request ID to every log entry
            structlog.contextvars.merge_contextvars,  # Merge context variables
            structlog.processors.add_log_level,  # Add log level
            structlog.processors.TimeStamper(fmt="iso"),  # ISO 8601 timestamps
            structlog.processors.StackInfoRenderer(),  # Render stack info
            structlog.processors.format_exc_info,  # Format exception tracebacks
            structlog.processors.JSONRenderer(),  # JSON output
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> WrappedLogger:
    """Get a logger instance for a module.

    Use the hybrid dotted namespace pattern: domain.component.action_state

    Pattern Format:
        {domain}.{component}.{action}_{state}

    Examples:
        - user.registration_started
        - user.registration_completed
        - product.create_started
        - product.create_completed
        - agent.tool.execution_started
        - agent.llm.call_completed

    Args:
        name: The logger name, typically __name__.

    Returns:
        A configured structlog logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user.login_started", username="alice")
        >>> try:
        ...     # do something
        ...     logger.info("user.login_completed", username="alice", user_id=123)
        ... except Exception:
        ...     logger.error("user.login_failed",
        ...                 username="alice",
        ...                 error="Invalid credentials",
        ...                 exc_info=True)

    See docs/logging-standard.md for complete event taxonomy and guidelines.
    """
    return structlog.get_logger(name)
