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
        "Be concise and precise.\n\n"
        "Available tools:\n"
        "- obsidian_query_vault_tool: Search and discover vault notes. Supports "
        "semantic keyword search, folder listing, related-note discovery by tags, "
        "metadata filtering (tags/date/folder), and recent changes. "
        "This is your ONLY tool right now.\n\n"
        "Always use obsidian_query_vault_tool when the user asks about their notes, "
        "vault contents, or anything that requires knowing what is actually stored. "
        "Never guess or fabricate vault contents — search first."
    ),
)

logger.info(
    "agent.lifecycle.initialized",
    model=_model_string,
    provider=settings.llm_provider,
)
