"""obsidian_query_vault_tool — vault discovery and search tool for vault_agent.

Importing this module registers obsidian_query_vault_tool on vault_agent via the
@vault_agent.tool decorator (side effect). Import through tool_registry.py only —
do not import directly in main.py or elsewhere.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import RunContext

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.logging import get_logger
from app.features.obsidian_query_vault.obsidian_query_vault_models import NoteInfo, QueryResult
from app.shared.vault.vault_manager import VaultManager

logger = get_logger(__name__)


@vault_agent.tool
async def obsidian_query_vault_tool(
    ctx: RunContext[AgentDependencies],
    query_type: Literal[
        "semantic_search",
        "list_structure",
        "find_related",
        "search_by_metadata",
        "recent_changes",
    ],
    query: str | None = None,
    path: str = "",
    reference_note: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 10,
    response_format: Literal["detailed", "concise"] = "concise",
) -> str:
    """Search and discover notes in the Obsidian vault (read-only).

    Use this when you need to:
    - Find notes matching a topic or keyword: use query_type="semantic_search" with query
    - Browse vault folders and files: use query_type="list_structure" with optional path
    - Discover notes related to a specific note via tags: use query_type="find_related"
    - Filter notes by tags, folder, or date range: use query_type="search_by_metadata"
    - See what was recently modified: use query_type="recent_changes"

    Do NOT use this for:
    - Reading the full content of a specific note (use obsidian_get_context_tool — coming soon)
    - Creating, updating, or deleting notes (use obsidian_vault_manager_tool — coming soon)
    - Retrieving a note when you already know its exact path (use obsidian_get_context_tool)

    Args:
        ctx: Agent context providing vault_path from request dependencies.
        query_type: The search operation to perform.
            - "semantic_search": Case-insensitive keyword search across all note content
              and frontmatter. Requires: query parameter.
            - "list_structure": List markdown files in a vault folder (non-recursive).
              Optional: path parameter (default: vault root).
            - "find_related": Find notes sharing frontmatter tags with a reference note,
              ranked by tag overlap count. Requires: reference_note parameter.
            - "search_by_metadata": Filter notes by tags, folder, and/or date range.
              Requires: filters parameter. Example:
              {"tags": ["urgent"], "folder": "Meetings", "date_range": {"days": 7}}
            - "recent_changes": List most recently modified markdown files.
              Optional: limit parameter (default: 10).
        query: Search text for semantic_search. Case-insensitive substring match.
            Required for query_type="semantic_search". Example: "machine learning"
        path: Vault-relative folder path for list_structure.
            Example: "Projects/2025". Default "" = vault root.
        reference_note: Vault-relative note path for find_related.
            Example: "Architecture/System Design.md"
        filters: Metadata filters for search_by_metadata. Supported keys:
            - "tags": list[str] — note must have ALL listed tags
            - "folder": str — restrict search to this vault-relative folder
            - "date_range": {"days": int} — modified within last N days
            Example: {"tags": ["project", "active"], "date_range": {"days": 30}}
        limit: Maximum results to return. Range 1-50 (values outside are clamped).
            Default: 10. Use 5 for top results, 20-50 for comprehensive listing.
        response_format: Output verbosity — affects token usage significantly.
            - "concise": path + title only (~30 tokens/result). DEFAULT. Use for
              navigation, large result sets, or when you just need paths.
            - "detailed": adds excerpt + tags + modified (~150 tokens/result). Use
              when you need content preview or metadata to answer the user.

    Returns:
        JSON-encoded QueryResult with fields:
            results (list[NoteInfo]): Matching notes. NoteInfo fields:
                path (str): Vault-relative path, e.g. "Projects/Alpha.md"
                title (str): Note title (H1 heading or filename stem)
                relevance (float): 0.0-1.0 score (1.0 for non-ranked results)
                excerpt (str|null): ~200-char content preview (detailed mode only)
                tags (list[str]|null): Frontmatter tags (detailed mode only)
                modified (str|null): ISO 8601 UTC timestamp (detailed mode only)
            total_found (int): Total matches before limit cutoff
            truncated (bool): True if more results exist beyond limit
            query_type (str): Echoes the executed query_type
            suggestion (str|null): Actionable guidance when empty or truncated

    Performance Notes:
        - concise: ~30 tokens/result (default — use for most queries)
        - detailed: ~150 tokens/result (5x cost — use only when metadata needed)
        - semantic_search: O(n) file scan, ~50-500ms for 1000-note vaults
        - recent_changes: O(n) mtime sort, ~20-100ms
        - list_structure: O(1) directory listing, ~5-20ms
        - find_related: O(n) frontmatter scan, ~50-500ms for 1000-note vaults
        - Max limit is 50 — values above 50 are silently clamped

    Examples:
        # Find notes about machine learning
        obsidian_query_vault_tool(
            query_type="semantic_search",
            query="machine learning",
            limit=10
        )

        # List files in the Projects folder
        obsidian_query_vault_tool(
            query_type="list_structure",
            path="Projects",
            response_format="concise"
        )

        # Find notes related to an architecture document
        obsidian_query_vault_tool(
            query_type="find_related",
            reference_note="Architecture/System Design.md",
            limit=5,
            response_format="detailed"
        )

        # Find urgent notes modified in the last week
        obsidian_query_vault_tool(
            query_type="search_by_metadata",
            filters={"tags": ["urgent"], "date_range": {"days": 7}},
            response_format="concise"
        )

        # See the 20 most recently changed files
        obsidian_query_vault_tool(
            query_type="recent_changes",
            limit=20,
            response_format="concise"
        )
    """
    effective_limit = min(max(1, limit), 50)
    start = time.time()

    logger.info(
        "vault.query.tool_started",
        query_type=query_type,
        limit=effective_limit,
        response_format=response_format,
        request_id=ctx.deps.request_id,
    )

    try:
        vault = VaultManager(ctx.deps.vault_path)
        result = _dispatch_query(
            vault=vault,
            query_type=query_type,
            query=query,
            path=path,
            reference_note=reference_note,
            filters=filters,
            limit=effective_limit,
            detailed=response_format == "detailed",
        )
    except ValueError as exc:
        logger.exception(
            "vault.query.tool_failed",
            query_type=query_type,
            fix_suggestion="Check VAULT_PATH env var and ensure vault directory is mounted",
        )
        return QueryResult(
            results=[],
            total_found=0,
            truncated=False,
            query_type=query_type,
            suggestion=str(exc),
        ).model_dump_json()

    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "vault.query.tool_completed",
        query_type=query_type,
        result_count=len(result.results),
        total_found=result.total_found,
        duration_ms=duration_ms,
        request_id=ctx.deps.request_id,
    )

    return result.model_dump_json()


def _dispatch_query(
    vault: VaultManager,
    query_type: str,
    query: str | None,
    path: str,
    reference_note: str | None,
    filters: dict[str, Any] | None,
    limit: int,
    detailed: bool,
) -> QueryResult:
    """Route query_type to the appropriate VaultManager operation.

    Args:
        vault: Initialized VaultManager instance.
        query_type: One of the Literal values from obsidian_query_vault_tool.
        query: Search text (semantic_search).
        path: Folder path (list_structure).
        reference_note: Reference note path (find_related).
        filters: Metadata filters (search_by_metadata).
        limit: Max results (already clamped 1-50).
        detailed: If True, populate excerpt/tags/modified on NoteInfo.

    Returns:
        Populated QueryResult.

    Raises:
        ValueError: If required parameters are missing or paths are invalid.
    """
    if query_type == "semantic_search":
        return _run_semantic_search(vault, query, limit, detailed)
    if query_type == "list_structure":
        return _run_list_structure(vault, path, limit, detailed)
    if query_type == "find_related":
        return _run_find_related(vault, reference_note, limit, detailed)
    if query_type == "search_by_metadata":
        return _run_search_by_metadata(vault, filters, limit, detailed)
    if query_type == "recent_changes":
        return _run_recent_changes(vault, limit, detailed)
    raise ValueError(f"Unknown query_type: '{query_type}'.")


def _run_semantic_search(
    vault: VaultManager, query: str | None, limit: int, detailed: bool
) -> QueryResult:
    """Execute semantic_search — keyword scan across all vault notes.

    Args:
        vault: VaultManager instance.
        query: Search text. Required.
        limit: Max results.
        detailed: Populate excerpt/tags/modified if True.

    Returns:
        QueryResult with matching notes.

    Raises:
        ValueError: If query is None or empty.
    """
    if not query:
        raise ValueError(
            "query parameter is required for semantic_search. Example: query='machine learning'"
        )

    matches = vault.search_content(query, limit=limit + 1)
    truncated = len(matches) > limit
    matches = matches[:limit]

    results = [_to_note_info(vault, fp, detailed=detailed, excerpt=exc) for fp, exc in matches]

    suggestion: str | None = None
    if not results:
        suggestion = f"No notes found matching '{query}'. Try broader terms or check spelling."
    elif truncated:
        suggestion = (
            f"Showing {limit} of {limit + 1}+ results. Narrow with filters or increase limit."
        )

    return QueryResult(
        results=results,
        total_found=len(results) + (1 if truncated else 0),
        truncated=truncated,
        query_type="semantic_search",
        suggestion=suggestion,
    )


def _run_list_structure(vault: VaultManager, path: str, limit: int, detailed: bool) -> QueryResult:
    """Execute list_structure — list markdown files in a vault folder.

    Args:
        vault: VaultManager instance.
        path: Vault-relative folder path. Empty string for root.
        limit: Max results.
        detailed: Populate tags/modified if True.

    Returns:
        QueryResult with files at the given path.
    """
    try:
        files = vault.list_markdown_files(folder=path, recursive=False)
    except ValueError as exc:
        return QueryResult(
            results=[],
            total_found=0,
            truncated=False,
            query_type="list_structure",
            suggestion=str(exc),
        )

    truncated = len(files) > limit
    visible = files[:limit]
    results = [_to_note_info(vault, fp, detailed=detailed) for fp in visible]

    suggestion: str | None = None
    if not results:
        label = f"'{path}'" if path else "vault root"
        suggestion = f"No markdown files found in {label}."
    elif truncated:
        suggestion = (
            f"Showing {limit} of {len(files)} files. Increase limit or navigate to a subfolder."
        )

    return QueryResult(
        results=results,
        total_found=len(files),
        truncated=truncated,
        query_type="list_structure",
        suggestion=suggestion,
    )


def _run_find_related(
    vault: VaultManager, reference_note: str | None, limit: int, detailed: bool
) -> QueryResult:
    """Execute find_related — discover notes sharing tags with a reference.

    Args:
        vault: VaultManager instance.
        reference_note: Vault-relative path to the reference note.
        limit: Max results.
        detailed: Populate tags/modified/excerpt if True.

    Returns:
        QueryResult with related notes ranked by tag overlap.

    Raises:
        ValueError: If reference_note is None or empty.
    """
    if not reference_note:
        raise ValueError(
            "reference_note parameter is required for find_related. "
            "Example: reference_note='Projects/Alpha.md'"
        )

    ref_path = vault.get_note_path(reference_note)
    if not ref_path.exists():
        return QueryResult(
            results=[],
            total_found=0,
            truncated=False,
            query_type="find_related",
            suggestion=(
                f"Note not found: '{reference_note}'. "
                f"Use query_type='semantic_search' to find available notes."
            ),
        )

    scored = vault.find_related_by_tags(ref_path, limit=limit + 1)
    truncated = len(scored) > limit
    scored = scored[:limit]

    results = [
        _to_note_info(vault, fp, detailed=detailed, relevance=min(overlap / 10.0, 1.0))
        for fp, overlap in scored
    ]

    suggestion: str | None = None
    if not results:
        suggestion = (
            "No related notes found. The note may have no tags, or no other notes share its tags."
        )
    elif truncated:
        suggestion = f"Showing {limit} most related notes. Increase limit for more."

    return QueryResult(
        results=results,
        total_found=len(results) + (1 if truncated else 0),
        truncated=truncated,
        query_type="find_related",
        suggestion=suggestion,
    )


def _run_search_by_metadata(
    vault: VaultManager,
    filters: dict[str, Any] | None,
    limit: int,
    detailed: bool,
) -> QueryResult:
    """Execute search_by_metadata — filter notes by tags, folder, date range.

    Args:
        vault: VaultManager instance.
        filters: Dict with optional keys: tags, folder, date_range.
        limit: Max results.
        detailed: Populate tags/modified/excerpt if True.

    Returns:
        QueryResult with matching notes.

    Raises:
        ValueError: If filters is None.
    """
    if not filters:
        raise ValueError(
            "filters parameter is required for search_by_metadata. "
            "Example: filters={'tags': ['urgent'], 'date_range': {'days': 7}}"
        )

    # Parse filter values with runtime type checks for mypy strict compatibility
    tags_raw = filters.get("tags")
    required_tags: list[str] = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]

    folder_raw = filters.get("folder")
    folder: str = folder_raw if isinstance(folder_raw, str) else ""

    date_range_raw = filters.get("date_range")
    days: int | None = None
    if isinstance(date_range_raw, dict):
        days_raw = date_range_raw.get("days")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if isinstance(days_raw, int):
            days = days_raw

    cutoff_mtime: float | None = time.time() - (days * 86400) if days is not None else None

    try:
        all_files = vault.list_markdown_files(folder=folder, recursive=True)
    except ValueError as exc:
        return QueryResult(
            results=[],
            total_found=0,
            truncated=False,
            query_type="search_by_metadata",
            suggestion=str(exc),
        )

    matched: list[Path] = []
    for file_path in all_files:
        if cutoff_mtime is not None and file_path.stat().st_mtime < cutoff_mtime:
            continue
        if required_tags:
            note_tags = set(vault.parse_frontmatter(file_path).get("tags", []))
            if not all(tag in note_tags for tag in required_tags):
                continue
        matched.append(file_path)

    truncated = len(matched) > limit
    visible = matched[:limit]
    results = [_to_note_info(vault, fp, detailed=detailed) for fp in visible]

    suggestion: str | None = None
    if not results:
        suggestion = "No notes matched the filters. Try relaxing tags or extending the date range."
    elif truncated:
        suggestion = f"Showing {limit} of {len(matched)} matches. Increase limit for more."

    return QueryResult(
        results=results,
        total_found=len(matched),
        truncated=truncated,
        query_type="search_by_metadata",
        suggestion=suggestion,
    )


def _run_recent_changes(vault: VaultManager, limit: int, detailed: bool) -> QueryResult:
    """Execute recent_changes — list most recently modified notes.

    Args:
        vault: VaultManager instance.
        limit: Max results.
        detailed: Populate tags/modified if True.

    Returns:
        QueryResult with recently modified notes.
    """
    recent = vault.get_recent_files(limit=limit + 1)
    truncated = len(recent) > limit
    recent = recent[:limit]

    results = [_to_note_info(vault, fp, detailed=detailed) for fp in recent]

    suggestion: str | None = None
    if not results:
        suggestion = "No markdown files found in the vault."
    elif truncated:
        suggestion = f"Showing {limit} most recent files. Increase limit to see more."

    return QueryResult(
        results=results,
        total_found=len(results) + (1 if truncated else 0),
        truncated=truncated,
        query_type="recent_changes",
        suggestion=suggestion,
    )


def _to_note_info(
    vault: VaultManager,
    file_path: Path,
    detailed: bool = False,
    excerpt: str | None = None,
    relevance: float = 1.0,
) -> NoteInfo:
    """Convert a filesystem Path to a NoteInfo response model.

    Args:
        vault: VaultManager instance for metadata helpers.
        file_path: Absolute Path to the note.
        detailed: If True, populate excerpt, tags, modified fields.
        excerpt: Pre-computed excerpt from search_content. Used only if detailed.
        relevance: Relevance score 0.0-1.0.

    Returns:
        NoteInfo populated according to detailed flag.
    """
    relative = vault.to_relative(file_path)
    title = vault.get_title(file_path)

    if not detailed:
        return NoteInfo(path=relative, title=title, relevance=relevance)

    frontmatter = vault.parse_frontmatter(file_path)
    tags_raw = frontmatter.get("tags", [])
    tags: list[str] | None = (
        [str(t) for t in tags_raw] if isinstance(tags_raw, list) and tags_raw else None  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    )

    return NoteInfo(
        path=relative,
        title=title,
        relevance=relevance,
        excerpt=excerpt,
        tags=tags,
        modified=vault.get_modified_iso(file_path),
    )
