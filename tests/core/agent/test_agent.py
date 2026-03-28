"""Unit tests for app.core.agent module."""

import os
from unittest.mock import patch

import pytest
from pydantic_ai import Agent


@pytest.mark.unit
def test_vault_agent_is_agent_instance(test_env_vars: dict[str, str]) -> None:
    """Test that vault_agent is a Pydantic AI Agent instance."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        from app.core.agent.agent import vault_agent

        assert isinstance(vault_agent, Agent)
    get_settings.cache_clear()


@pytest.mark.unit
def test_agent_dependencies_defaults() -> None:
    """Test AgentDependencies can be instantiated with default values."""
    from app.core.agent.dependencies import AgentDependencies

    deps = AgentDependencies()
    assert deps.request_id == ""


@pytest.mark.unit
def test_agent_dependencies_with_request_id() -> None:
    """Test AgentDependencies stores the provided request_id."""
    from app.core.agent.dependencies import AgentDependencies

    deps = AgentDependencies(request_id="test-correlation-id")
    assert deps.request_id == "test-correlation-id"


@pytest.mark.unit
def test_model_string_format(test_env_vars: dict[str, str]) -> None:
    """Test the model string is built correctly as 'provider:model'."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        get_settings.cache_clear()
        settings = get_settings()
        model_string = f"{settings.llm_provider}:{settings.llm_model}"
        assert ":" in model_string
        assert model_string == "anthropic:claude-haiku-4-5-20251001"
    get_settings.cache_clear()
