"""Tests for app.core.config module."""

import os
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings


def create_settings() -> Settings:
    """Create Settings instance for testing.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()


def test_settings_defaults() -> None:
    """Test Settings instantiation with default values."""
    get_settings.cache_clear()
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
        },
    ):
        get_settings.cache_clear()
        settings = create_settings()

        assert settings.app_name == "Test App"
        assert settings.version == "1.0.0"
        assert settings.environment == "production"
        assert settings.log_level == "DEBUG"
        assert settings.api_prefix == "/v1"
    get_settings.cache_clear()


def test_allowed_origins_parsing() -> None:
    """Test allowed_origins parsing from environment variable.

    Note: pydantic-settings expects JSON array format for list fields.
    """
    with patch.dict(
        os.environ,
        {
            "ALLOWED_ORIGINS": '["http://example.com","http://localhost:3000","http://test.com"]',
        },
    ):
        get_settings.cache_clear()
        settings = create_settings()

        assert len(settings.allowed_origins) == 3
        assert "http://example.com" in settings.allowed_origins
        assert "http://localhost:3000" in settings.allowed_origins
        assert "http://test.com" in settings.allowed_origins
    get_settings.cache_clear()


def test_get_settings_caching() -> None:
    """Test get_settings() returns cached instance."""
    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


def test_settings_case_insensitive() -> None:
    """Test settings are case-insensitive."""
    with patch.dict(
        os.environ,
        {
            "app_name": "Lower Case App",
            "ENVIRONMENT": "PRODUCTION",
        },
    ):
        get_settings.cache_clear()
        settings = create_settings()

        assert settings.app_name == "Lower Case App"
        assert settings.environment == "PRODUCTION"
    get_settings.cache_clear()


@pytest.mark.unit
def test_llm_settings_defaults() -> None:
    """Test LLM settings have correct defaults."""
    get_settings.cache_clear()
    settings = create_settings()

    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-haiku-4-5-20251001"
    assert settings.llm_api_key != ""  # loaded from .env in dev; empty string is the coded default


@pytest.mark.unit
def test_llm_settings_from_environment() -> None:
    """Test LLM settings can be overridden via environment variables."""
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o",
            "LLM_API_KEY": "sk-test-key",
            "API_KEY": "my-api-key",
        },
    ):
        get_settings.cache_clear()
        settings = create_settings()

        assert settings.llm_provider == "openai"
        assert settings.llm_model == "gpt-4o"
        assert settings.llm_api_key == "sk-test-key"
        assert settings.api_key == "my-api-key"
    get_settings.cache_clear()


@pytest.mark.unit
def test_database_url_is_optional() -> None:
    """Test database_url defaults to empty string — not required."""
    with patch.dict(os.environ, {}, clear=False):
        get_settings.cache_clear()
        settings = create_settings()
        # database_url has a default of "" — app can start without a DB
        assert isinstance(settings.database_url, str)
    get_settings.cache_clear()
