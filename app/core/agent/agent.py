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
        "metadata filtering (tags/date/folder), and recent changes. Returns summaries "
        "and excerpts only — use this to find note paths.\n"
        "- obsidian_get_context_tool: Read full note content with optional context. "
        "Supports reading a single note, multiple notes, tag-related notes, daily notes, "
        "and notes with backlinks. Use this after obsidian_query_vault_tool to read "
        "content for synthesis, answering questions, or analysis.\n"
        "- obsidian_note_manager_tool: Create, update, append, delete, and move notes "
        "and folders. Supports bulk tagging and bulk metadata updates. Always use "
        "obsidian_query_vault_tool to confirm note paths BEFORE passing them to this tool.\n\n"
        "Workflow: discover with obsidian_query_vault_tool → read with "
        "obsidian_get_context_tool → modify with obsidian_note_manager_tool. "
        "Never guess vault paths — search first."
    ),
)

logger.info(
    "agent.lifecycle.initialized",
    model=_model_string,
    provider=settings.llm_provider,
)
