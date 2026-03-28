"""Shared fixtures for root tests/ directory."""

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_env_vars() -> dict[str, str]:
    """Provide minimal environment variables for unit testing.

    Returns:
        Dict of env vars satisfying all Settings fields without real credentials.
    """
    return {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-haiku-4-5-20251001",
        "LLM_API_KEY": "test-key-not-real",
        "API_KEY": "test-bearer-token",
    }


@pytest.fixture
def app_client(test_env_vars: dict[str, str]) -> Generator[TestClient, None, None]:
    """Create a TestClient with test environment variables patched.

    Clears the settings cache before and after to prevent cross-test pollution.

    Args:
        test_env_vars: Test environment variables fixture.

    Yields:
        Configured FastAPI TestClient.
    """
    from app.core.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        yield TestClient(app)
    get_settings.cache_clear()
