"""obsidian_note_manager_tool — vault modification tool for vault_agent.

Importing this module registers obsidian_note_manager_tool on vault_agent via the
@vault_agent.tool decorator (side effect). Import through tool_registry.py only —
do not import directly in main.py or elsewhere.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic_ai import RunContext

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.logging import get_logger
from app.features.obsidian_note_manager.obsidian_note_manager_models import NoteManagerResult
from app.features.obsidian_note_manager.obsidian_note_manager_service import NoteManagerService
from app.shared.vault.vault_manager import VaultManager

logger = get_logger(__name__)


@vault_agent.tool
async def obsidian_note_manager_tool(
    ctx: RunContext[AgentDependencies],
    operation: Literal[
        "create_note",
        "update_note",
        "append_note",
        "delete_note",
        "move_note",
        "create_folder",
        "delete_folder",
        "move_folder",
        "bulk_tag",
        "bulk_move",
        "bulk_update_metadata",
    ],
    target: str | None = None,
    targets: list[str] | None = None,
    content: str | None = None,
    destination: str | None = None,
    metadata: dict[str, object] | None = None,
    metadata_changes: dict[str, object] | None = None,
    confirm_destructive: bool = False,
    create_folders: bool = True,
) -> str:
    """Create, update, move, delete, and organise notes and folders in the Obsidian vault.

    Use this when you need to:
    - Create a new note with optional frontmatter: operation="create_note"
    - Replace the entire content of an existing note: operation="update_note"
    - Append text to the end of an existing note: operation="append_note"
    - Permanently delete a note (requires confirm_destructive=True): operation="delete_note"
    - Move a note to a different location: operation="move_note"
    - Create a new folder (including nested paths): operation="create_folder"
    - Delete a folder and its contents (requires confirm_destructive=True): operation="delete_folder"
    - Move a folder to a new location: operation="move_folder"
    - Add/replace tags on multiple notes at once: operation="bulk_tag"
    - Move multiple notes to a destination folder: operation="bulk_move"
    - Update frontmatter fields on multiple notes: operation="bulk_update_metadata"

    Do NOT use this for:
    - Finding notes or browsing vault structure (use obsidian_query_vault_tool instead)
    - Reading note content (use obsidian_query_vault_tool with query_type="semantic_search")
    - Discovering note paths — always use obsidian_query_vault_tool first to confirm paths
      exist before passing them to this tool

    Args:
        ctx: Agent context providing vault_path and request_id from dependencies.
        operation: The modification to perform. Choose based on what you want to change:
            - "create_note": Create a new .md file. Requires: target. Optional: content, metadata.
            - "update_note": Replace entire note content. Requires: target, content.
            - "append_note": Add text to end of note. Requires: target, content.
            - "delete_note": Permanently delete a note. Requires: target, confirm_destructive=True.
            - "move_note": Move note to new path. Requires: target, destination.
            - "create_folder": Create directory. Requires: target (folder path).
            - "delete_folder": Delete folder recursively. Requires: target, confirm_destructive=True.
            - "move_folder": Move directory. Requires: target, destination.
            - "bulk_tag": Update frontmatter on many notes. Requires: targets, metadata.
            - "bulk_move": Move many notes to one folder. Requires: targets, destination.
            - "bulk_update_metadata": Set frontmatter fields on many notes. Requires: targets,
              metadata_changes.
        target: Vault-relative path for single-item operations.
            Examples: "Projects/Alpha.md", "Archive/2024", "Inbox/Draft.md"
            Do NOT include the vault root — just the relative path.
        targets: List of vault-relative paths for bulk operations.
            Use obsidian_query_vault_tool to obtain paths before passing here.
            Example: ["Projects/Alpha.md", "Projects/Beta.md", "Daily/2025-01-15.md"]
        content: Note body text for create_note, update_note, append_note.
            Supports full Markdown including headings, lists, and code blocks.
        destination: Target path for move operations (move_note, move_folder, bulk_move).
            For bulk_move: folder path only (filename is preserved from source).
            For move_note/move_folder: full destination path including name.
            Example: "Archive/OldProjects", "Projects/Renamed.md"
        metadata: Frontmatter key-value pairs for create_note and bulk_tag.
            Example: {"tags": ["project", "active"], "status": "planning", "priority": "high"}
            Lists become YAML inline lists: [project, active]
        metadata_changes: Frontmatter changes to merge into notes for bulk_update_metadata.
            Example: {"status": "reviewed", "reviewed_date": "2025-01-15"}
        confirm_destructive: Safety flag required for delete_note and delete_folder.
            Default: False. Set to True only when you intend to permanently delete.
            The tool will return a failure result (not raise) if this is False for deletes.
        create_folders: Whether to auto-create missing parent directories (default: True).
            Applies to create_note, move_note, create_folder. Usually leave as True.

    Returns:
        JSON-encoded NoteManagerResult with fields:
            success (bool): True if operation completed (fully or partially for bulk ops).
            operation (str): The operation that was executed.
            affected_count (int): Number of items successfully modified.
            affected_paths (list[str]): Vault-relative paths of modified items.
            message (str): Human-readable summary — read this on failure for guidance.
            warnings (list[str]|null): Non-fatal issues encountered.
            partial_success (bool|null): True for bulk ops where some items failed.
            failures (list|null): Per-item failure details for bulk ops.
                Each failure has: path (str), reason (str).

    Performance Notes:
        - Single note operations (create, update, append, delete, move): ~5-30ms
        - Folder operations: ~5-20ms
        - Bulk operations: ~10ms per note (scales linearly with targets list length)
        - Response size: ~100-200 tokens for single ops; ~150-300 tokens for bulk ops
        - Max bulk targets: no hard limit, but >50 notes may be slow (~500ms+)
        - All operations are atomic per-item — bulk failures do not roll back successes

    Examples:
        # Create a project note with frontmatter
        obsidian_note_manager_tool(
            operation="create_note",
            target="Projects/2025/Website Redesign.md",
            content="# Website Redesign\n\nProject goals and timeline.",
            metadata={"tags": ["project", "active"], "status": "planning"}
        )

        # Append meeting notes to today's daily note
        obsidian_note_manager_tool(
            operation="append_note",
            target="Daily/2025-01-15.md",
            content="\\n## Afternoon Meeting\\n- Discussed Q1 roadmap\\n- Action: update project board"
        )

        # Move a note to the archive (confirm path first with obsidian_query_vault_tool)
        obsidian_note_manager_tool(
            operation="move_note",
            target="Projects/Old Project.md",
            destination="Archive/2024/Old Project.md"
        )

        # Delete a draft permanently
        obsidian_note_manager_tool(
            operation="delete_note",
            target="Inbox/scratch-notes.md",
            confirm_destructive=True
        )

        # Tag all notes returned from a previous query as "reviewed"
        obsidian_note_manager_tool(
            operation="bulk_tag",
            targets=["Meetings/2025-01-12.md", "Meetings/2025-01-13.md", "Meetings/2025-01-14.md"],
            metadata={"tags": ["meeting", "reviewed"]}
        )

        # Move all inbox notes to a processing folder
        obsidian_note_manager_tool(
            operation="bulk_move",
            targets=["Inbox/Note1.md", "Inbox/Note2.md", "Inbox/Note3.md"],
            destination="Processing"
        )
    """
    start = time.time()

    logger.info(
        "vault.note_manager.tool_started",
        operation=operation,
        target=target,
        target_count=len(targets) if targets else None,
        request_id=ctx.deps.request_id,
    )

    try:
        vault = VaultManager(ctx.deps.vault_path)
    except ValueError as exc:
        logger.exception(
            "vault.note_manager.vault_init_failed",
            operation=operation,
            vault_path=ctx.deps.vault_path,
            fix_suggestion="Check VAULT_PATH env var and ensure vault directory is mounted",
        )
        return NoteManagerResult(
            success=False,
            operation=operation,
            affected_count=0,
            affected_paths=[],
            message=str(exc),
        ).model_dump_json()

    service = NoteManagerService(vault)
    result = service.dispatch(
        operation,
        target=target,
        targets=targets,
        content=content,
        destination=destination,
        metadata=metadata,
        metadata_changes=metadata_changes,
        confirm_destructive=confirm_destructive,
        create_folders=create_folders,
    )

    duration_ms = round((time.time() - start) * 1000, 2)

    if result.success:
        logger.info(
            "vault.note_manager.tool_completed",
            operation=operation,
            affected_count=result.affected_count,
            partial_success=result.partial_success,
            duration_ms=duration_ms,
            request_id=ctx.deps.request_id,
        )
    else:
        logger.warning(
            "vault.note_manager.tool_returned_failure",
            operation=operation,
            message=result.message,
            duration_ms=duration_ms,
            request_id=ctx.deps.request_id,
        )

    return result.model_dump_json()
