"""Tests for shared utility functions."""

from datetime import UTC, datetime

from app.shared.utils import format_iso, utcnow


def test_utcnow_returns_timezone_aware_datetime() -> None:
    """Test that utcnow returns a timezone-aware datetime."""
    now = utcnow()

    # Verify it's a datetime
    assert isinstance(now, datetime)

    # Verify it has timezone information
    assert now.tzinfo is not None

    # Verify it's in UTC
    assert now.tzinfo.utcoffset(None) == UTC.utcoffset(None)


def test_utcnow_returns_current_time() -> None:
    """Test that utcnow returns approximately the current time."""
    before = datetime.now(UTC)
    now = utcnow()
    after = datetime.now(UTC)

    # Verify the returned time is between before and after
    assert before <= now <= after


def test_format_iso_returns_iso_8601_string() -> None:
    """Test that format_iso returns ISO 8601 formatted string."""
    dt = datetime(2025, 10, 29, 14, 30, 0, tzinfo=UTC)
    iso_string = format_iso(dt)

    # Verify it's a string
    assert isinstance(iso_string, str)

    # Verify it contains expected components
    assert "2025-10-29" in iso_string
    assert "14:30:00" in iso_string

    # Verify it can be parsed back to datetime
    parsed = datetime.fromisoformat(iso_string)
    assert parsed == dt


def test_format_iso_with_timezone_aware_datetime() -> None:
    """Test format_iso with timezone-aware datetime."""
    dt = utcnow()
    iso_string = format_iso(dt)

    # Verify timezone info is included in the string
    assert "+" in iso_string or "Z" in iso_string.upper()

    # Verify it can be parsed back
    parsed = datetime.fromisoformat(iso_string)
    assert parsed.tzinfo is not None


def test_format_iso_with_microseconds() -> None:
    """Test format_iso preserves microsecond precision."""
    dt = datetime(2025, 10, 29, 14, 30, 0, 123456, tzinfo=UTC)
    iso_string = format_iso(dt)

    # Verify microseconds are included
    assert "123456" in iso_string

    # Verify precision is maintained when parsing back
    parsed = datetime.fromisoformat(iso_string)
    assert parsed.microsecond == 123456
