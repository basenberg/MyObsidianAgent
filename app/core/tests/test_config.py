"""Tests for app.core.config module."""

import os
from unittest.mock import patch

from app.core.config import Settings, get_settings


def create_settings() -> Settings:
    """Create Settings instance for testing.

    Helper function for creating Settings in tests. pydantic-settings loads
    required fields from environment variables at runtime. Mypy's static analysis
    doesn't understand this and expects constructor arguments. This is a known
    limitation with pydantic-settings, so we suppress the call-arg error.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()  # type: ignore[call-arg]


def test_settings_defaults() -> None:
    """Test Settings instantiation with default values."""
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
            "LOG_LEVEL": "INFO",  # Override .env file to test default value
        },
    ):
        settings = create_settings()

        assert settings.app_name == "Obsidian Agent Project"
        assert settings.version == "0.1.0"
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.api_prefix == "/api"
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://localhost:8123" in settings.allowed_origins


def test_settings_from_environment() -> None:
    """Test Settings can be overridden by environment variables."""
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "Test App",
            "VERSION": "1.0.0",
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "API_PREFIX": "/v1",
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert settings.app_name == "Test App"
        assert settings.version == "1.0.0"
        assert settings.environment == "production"
        assert settings.log_level == "DEBUG"
        assert settings.api_prefix == "/v1"


def test_allowed_origins_parsing() -> None:
    """Test allowed_origins parsing from environment variable.

    Note: pydantic-settings expects JSON array format for list fields.
    """
    with patch.dict(
        os.environ,
        {
            "ALLOWED_ORIGINS": '["http://example.com","http://localhost:3000","http://test.com"]',
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert len(settings.allowed_origins) == 3
        assert "http://example.com" in settings.allowed_origins
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://test.com" in settings.allowed_origins


def test_get_settings_caching() -> None:
    """Test get_settings() returns cached instance."""
    # Clear the cache first
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    # Should return the same instance (cached)
    assert settings1 is settings2


def test_settings_case_insensitive() -> None:
    """Test settings are case-insensitive."""
    with patch.dict(
        os.environ,
        {
            "app_name": "Lower Case App",
            "ENVIRONMENT": "PRODUCTION",
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        },
    ):
        settings = create_settings()

        assert settings.app_name == "Lower Case App"
        assert settings.environment == "PRODUCTION"
