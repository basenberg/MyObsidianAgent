"""Pydantic AI vault agent singleton.

This module defines vault_agent — the single Agent instance used across all
features. Tools register themselves via @vault_agent.tool decorators in their
own feature modules. main.py imports those modules as side effects to trigger
registration.

Usage:
    from app.core.agent.agent import vault_agent
"""

import os

from pydantic_ai import Agent

from app.core.agent.dependencies import AgentDependencies
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()
_model_string: str = f"{settings.llm_provider}:{settings.llm_model}"

# Bridge our provider-agnostic LLM_API_KEY to the provider-specific env var
# that pydantic-ai resolves at model construction time.
_PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}
if settings.llm_api_key and settings.llm_provider in _PROVIDER_ENV_VARS:
    os.environ[_PROVIDER_ENV_VARS[settings.llm_provider]] = settings.llm_api_key

vault_agent: Agent[AgentDependencies, str] = Agent(
    _model_string,
    deps_type=AgentDependencies,
    instructions=(
        "You are Paddy, an AI assistant for an Obsidian knowledge vault. "
        "Help the user query, read, and manage their notes. "
        "Be concise and precise. When tools are available, prefer them over guessing."
    ),
)

logger.info(
    "agent.lifecycle.initialized",
    model=_model_string,
    provider=settings.llm_provider,
)
