"""obsidian_get_context_tools — vault context reading tool for vault_agent.

Importing this module registers obsidian_get_context_tool on vault_agent via the
@vault_agent.tool decorator (side effect). Import through tool_registry.py only.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic_ai import RunContext

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.logging import get_logger
from app.features.obsidian_get_context.obsidian_get_context_models import ContextResult, NoteContent
from app.features.obsidian_get_context.obsidian_get_context_service import GetContextService
from app.shared.vault.vault_manager import VaultManager

logger = get_logger(__name__)


@vault_agent.tool
async def obsidian_get_context_tool(
    ctx: RunContext[AgentDependencies],
    context_type: Literal[
        "read_note",
        "read_multiple",
        "gather_related",
        "daily_note",
        "note_with_backlinks",
    ],
    target: str | None = None,
    targets: list[str] | None = None,
    date: str | None = None,
    include_metadata: bool = True,
    include_backlinks: bool = False,
    max_related: int = 3,
    response_format: Literal["detailed", "concise"] = "detailed",
) -> str:
    """Read full note content with optional context for analysis and synthesis.

    Use this when you need to:
    - Read a single note's full content with metadata: use context_type="read_note"
    - Read several notes together for comparison: use context_type="read_multiple"
    - Read a note and its tag-related notes: use context_type="gather_related"
    - Get today's or a specific daily note: use context_type="daily_note"
    - Read a note and all notes that link to it: use context_type="note_with_backlinks"

    Do NOT use this for:
    - Discovering or searching for notes (use obsidian_query_vault_tool first to find paths)
    - Creating, updating, or deleting notes (use obsidian_vault_manager_tool)

    Args:
        ctx: Agent context providing vault_path from request dependencies.
        context_type: The reading operation to perform.
            - "read_note": Read full content of a single note. Requires: target.
              Optional: include_metadata, include_backlinks, response_format.
            - "read_multiple": Read several notes in one call. Requires: targets list.
              Returns first as primary_note, rest as related_notes.
            - "gather_related": Read a note plus notes sharing its tags. Requires: target.
              Optional: max_related (default 3). Note must have frontmatter tags.
            - "daily_note": Read today's or a specific daily note. Optional: date
              parameter ("today" or "2025-01-15"). Searches Daily Notes/, Journal/, root.
            - "note_with_backlinks": Read a note plus notes that wiki-link to it.
              Requires: target. Optional: max_related.
        target: Vault-relative note path for single-note operations.
            Example: "Projects/ML Project.md"
        targets: List of vault-relative paths for read_multiple.
            Example: ["Projects/Alpha.md", "Projects/Beta.md"]
        date: Date for daily_note. "today" or ISO format "2025-01-15".
            Default: "today" when not provided.
        include_metadata: Whether to include frontmatter in response. Default: True.
            Set False to reduce tokens when metadata is not needed.
        include_backlinks: Whether to find notes linking to target (read_note only).
            Default: False. Set True only when backlink analysis is needed.
        max_related: Maximum related notes or backlinks to return. Default: 3.
            Range 1-10 recommended. Higher values increase token cost significantly.
        response_format: Output verbosity.
            - "detailed": Full note content. Default. Use for synthesis and answering questions.
            - "concise": First 200 words of content. Use for quick summaries or when
              token budget is tight (~100-300 tokens vs 500-5000 for detailed).

    Returns:
        JSON-encoded ContextResult with fields:
            primary_note (NoteContent): The main note. Fields: path, title, content,
                metadata (dict|null), word_count.
            related_notes (list[NoteContent]|null): Additional notes for multi-note operations.
            backlinks (list[BacklinkInfo]|null): Notes linking to primary_note. Fields:
                note_path, note_title, context (surrounding text with the link).
            metadata_summary (dict|null): Frontmatter of primary note (when include_metadata).
            token_estimate (int): Approximate token count of this response.
            context_type (str): The context_type that was executed.
            error (str|null): Actionable error message if operation failed.

    Performance Notes:
        - detailed: ~500-5000 tokens depending on note length
        - concise: ~100-300 tokens (first 200 words only)
        - gather_related with max_related=3: ~1500-15000 tokens total (detailed)
        - note_with_backlinks: adds ~200-500 tokens per backlink
        - Always run obsidian_query_vault_tool first to get exact note paths

    Examples:
        # Read single note with metadata
        obsidian_get_context_tool(
            context_type="read_note",
            target="Projects/ML Project.md",
            include_metadata=True
        )

        # Get today's daily note
        obsidian_get_context_tool(
            context_type="daily_note",
            date="today"
        )

        # Read multiple notes for comparison
        obsidian_get_context_tool(
            context_type="read_multiple",
            targets=["Projects/Alpha.md", "Projects/Beta.md"],
            response_format="concise"
        )

        # Read note with its related notes
        obsidian_get_context_tool(
            context_type="gather_related",
            target="Architecture/System Design.md",
            max_related=5
        )

        # Read note with backlinks
        obsidian_get_context_tool(
            context_type="note_with_backlinks",
            target="Concepts/Zettelkasten.md",
            max_related=10
        )
    """
    start = time.time()
    logger.info(
        "vault.context.tool_started",
        context_type=context_type,
        request_id=ctx.deps.request_id,
    )

    try:
        vault = VaultManager(ctx.deps.vault_path)
        service = GetContextService(vault)
        result = service.dispatch(
            context_type,
            target=target,
            targets=targets,
            date=date,
            include_metadata=include_metadata,
            include_backlinks=include_backlinks,
            max_related=max_related,
            concise=response_format == "concise",
        )
    except (ValueError, OSError) as exc:
        logger.exception(
            "vault.context.tool_failed",
            context_type=context_type,
            fix_suggestion="Verify note path with obsidian_query_vault_tool first",
        )
        result = ContextResult(
            primary_note=NoteContent(path="", title="error", content=str(exc), word_count=0),
            context_type=context_type,
            error=str(exc),
        )

    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "vault.context.tool_completed",
        context_type=context_type,
        duration_ms=duration_ms,
    )
    return result.model_dump_json()
