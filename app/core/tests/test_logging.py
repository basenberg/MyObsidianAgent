"""Unit tests for structured logging module."""

import json
from io import StringIO

import pytest
import structlog

from app.core.logging import (
    add_request_id,
    get_logger,
    get_request_id,
    request_id_var,
    set_request_id,
    setup_logging,
)


@pytest.fixture(autouse=True)
def reset_request_id() -> None:
    """Reset request ID context variable before each test."""
    request_id_var.set("")


@pytest.fixture
def captured_logs() -> StringIO:
    """Fixture to capture log output."""
    return StringIO()


def test_set_request_id_generates_uuid_when_none() -> None:
    """Test that set_request_id generates a UUID when none provided."""
    request_id = set_request_id()

    assert request_id
    assert len(request_id) == 36  # UUID format length
    assert "-" in request_id


def test_set_request_id_uses_provided_value() -> None:
    """Test that set_request_id uses provided value."""
    custom_id = "custom-request-123"
    request_id = set_request_id(custom_id)

    assert request_id == custom_id
    assert get_request_id() == custom_id


def test_get_request_id_returns_empty_when_not_set() -> None:
    """Test that get_request_id returns empty string when not set."""
    result = get_request_id()
    assert result == ""


def test_get_request_id_returns_set_value() -> None:
    """Test that get_request_id returns previously set value."""
    expected_id = "test-request-456"
    set_request_id(expected_id)

    result = get_request_id()
    assert result == expected_id


def test_add_request_id_processor_adds_id_to_event_dict() -> None:
    """Test that add_request_id processor adds request_id to event dict."""
    set_request_id("test-id-789")
    event_dict: dict[str, str] = {"event": "test.event"}

    result = add_request_id(None, "info", event_dict)

    assert "request_id" in result
    assert result["request_id"] == "test-id-789"


def test_add_request_id_processor_skips_when_no_id() -> None:
    """Test that add_request_id processor doesn't add empty request_id."""
    event_dict: dict[str, str] = {"event": "test.event"}

    result = add_request_id(None, "info", event_dict)

    assert "request_id" not in result


def test_setup_logging_configures_structlog() -> None:
    """Test that setup_logging properly configures structlog."""
    setup_logging(log_level="DEBUG")

    # Verify logger can be retrieved
    logger = structlog.get_logger("test")
    assert logger is not None


def test_get_logger_returns_structlog_instance() -> None:
    """Test that get_logger returns a structlog logger instance."""
    setup_logging()
    logger = get_logger("test.module")

    assert logger is not None
    # Verify it has structlog methods
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "debug")


def test_logging_produces_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that logging produces valid JSON output."""
    setup_logging(log_level="INFO")
    logger = get_logger("test")

    logger.info("test.operation_started", key="value", count=42)

    captured = capsys.readouterr()
    log_line = captured.out.strip()

    # Parse JSON to verify format
    log_data = json.loads(log_line)
    assert log_data["event"] == "test.operation_started"
    assert log_data["key"] == "value"
    assert log_data["count"] == 42
    assert "timestamp" in log_data
    assert log_data["level"] == "info"


def test_logging_includes_request_id_when_set(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that logs include request_id when set in context."""
    setup_logging(log_level="INFO")
    logger = get_logger("test")

    test_request_id = "correlation-id-123"
    set_request_id(test_request_id)

    logger.info("test.operation_started")

    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())

    assert log_data["request_id"] == test_request_id


def test_logging_formats_exceptions(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that exc_info=True includes formatted exception in JSON."""
    setup_logging(log_level="ERROR")
    logger = get_logger("test")

    try:
        raise ValueError("Test error message")
    except ValueError:
        logger.error("test.operation_failed", exc_info=True)

    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())

    assert log_data["event"] == "test.operation_failed"
    assert log_data["level"] == "error"
    assert "exception" in log_data
    assert "ValueError: Test error message" in log_data["exception"]
    assert "Traceback" in log_data["exception"]


def test_logging_consistent_event_naming(capsys: pytest.CaptureFixture[str]) -> None:
    """Test consistent event naming pattern: domain.component.action_state."""
    setup_logging(log_level="INFO")
    logger = get_logger("test")

    # Test the recommended hybrid naming pattern
    logger.info("product.create_started", sku="TEST-001")
    logger.info("product.create_completed", sku="TEST-001", product_id=123)

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")

    log1 = json.loads(lines[0])
    log2 = json.loads(lines[1])

    assert log1["event"] == "product.create_started"
    assert log1["sku"] == "TEST-001"

    assert log2["event"] == "product.create_completed"
    assert log2["sku"] == "TEST-001"
    assert log2["product_id"] == 123


def test_logging_different_levels(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that different log levels are properly recorded."""
    setup_logging(log_level="DEBUG")
    logger = get_logger("test")

    logger.debug("test.debug_event")
    logger.info("test.info_event")
    logger.warning("test.warning_event")
    logger.error("test.error_event")

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")

    assert len(lines) == 4

    levels = [json.loads(line)["level"] for line in lines]
    assert levels == ["debug", "info", "warning", "error"]


def test_logging_respects_log_level_filter(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that log level filtering works correctly."""
    setup_logging(log_level="WARNING")
    logger = get_logger("test")

    logger.debug("test.debug_event")  # Should not appear
    logger.info("test.info_event")  # Should not appear
    logger.warning("test.warning_event")  # Should appear
    logger.error("test.error_event")  # Should appear

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")

    # Only WARNING and ERROR should be logged
    assert len(lines) == 2

    log_data = [json.loads(line) for line in lines]
    assert log_data[0]["level"] == "warning"
    assert log_data[1]["level"] == "error"


def test_logging_with_structured_data(capsys: pytest.CaptureFixture[str]) -> None:
    """Test logging with complex structured data."""
    setup_logging(log_level="INFO")
    logger = get_logger("test")

    logger.info(
        "order.create_completed",
        order_id=12345,
        customer_id=67890,
        total=99.99,
        items_count=3,
        status="pending",
    )

    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())

    assert log_data["event"] == "order.create_completed"
    assert log_data["order_id"] == 12345
    assert log_data["customer_id"] == 67890
    assert log_data["total"] == 99.99
    assert log_data["items_count"] == 3
    assert log_data["status"] == "pending"
