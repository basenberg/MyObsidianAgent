"""NoteManagerService — business logic for all vault modification operations.

This module is deliberately decoupled from Pydantic AI (no RunContext dependency),
making every operation directly unit-testable without constructing an agent run.

The service is instantiated per-request inside obsidian_note_manager_tool.py:
    service = NoteManagerService(VaultManager(ctx.deps.vault_path))
    result = service.dispatch(operation, **kwargs)
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.features.obsidian_note_manager.obsidian_note_manager_models import (
    BulkOperationFailure,
    NoteManagerResult,
)
from app.shared.vault.vault_manager import VaultManager

logger = get_logger(__name__)


class NoteManagerService:
    """Business logic for Obsidian vault modification operations.

    Wraps VaultManager write methods with validation, safety guards, and
    bulk coordination. All methods return NoteManagerResult — never raise.

    Args:
        vault: Initialised VaultManager pointed at the vault root.
    """

    def __init__(self, vault: VaultManager) -> None:
        """Initialise with a VaultManager instance.

        Args:
            vault: VaultManager instance for the target vault.
        """
        self._vault = vault

    # -------------------------------------------------------------------------
    # Single-note operations
    # -------------------------------------------------------------------------

    def create_note(
        self,
        target: str | None,
        content: str | None,
        metadata: dict[str, object] | None,
        _create_folders: bool,
    ) -> NoteManagerResult:
        """Create a new markdown note, optionally with YAML frontmatter.

        Args:
            target: Vault-relative path for the new note (e.g., "Projects/Alpha.md").
            content: Body content of the note.
            metadata: Optional frontmatter key-value pairs.
            _create_folders: Unused — VaultManager.write_note always creates parent dirs.

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="create_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    "create_note requires a target path. Example: target='Projects/NewNote.md'"
                ),
            )

        body = content or ""
        final_content = self._build_content_with_frontmatter(body, metadata) if metadata else body

        try:
            path = self._vault.write_note(target, final_content, overwrite=False)
            relative = self._vault.to_relative(path)
            return NoteManagerResult(
                success=True,
                operation="create_note",
                affected_count=1,
                affected_paths=[relative],
                message=f"Note created at '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="create_note",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    def update_note(
        self,
        target: str | None,
        content: str | None,
    ) -> NoteManagerResult:
        """Replace the full content of an existing note.

        Args:
            target: Vault-relative path to the note.
            content: New full content (replaces entire file).

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="update_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    "update_note requires a target path. "
                    "Use obsidian_query_vault_tool to find the note path first."
                ),
            )

        try:
            path = self._vault.write_note(target, content or "", overwrite=True)
            relative = self._vault.to_relative(path)
            return NoteManagerResult(
                success=True,
                operation="update_note",
                affected_count=1,
                affected_paths=[relative],
                message=f"Note updated at '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="update_note",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    def append_note(
        self,
        target: str | None,
        content: str | None,
    ) -> NoteManagerResult:
        """Append text to the end of an existing note.

        Args:
            target: Vault-relative path to the note.
            content: Text to append.

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="append_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    "append_note requires a target path. "
                    "Use obsidian_query_vault_tool to find the note path first."
                ),
            )

        note_path = self._vault.get_note_path(target)
        if not note_path.exists():
            return NoteManagerResult(
                success=False,
                operation="append_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    f"Note not found at '{target}'. "
                    f"Use obsidian_query_vault_tool to find available notes."
                ),
            )

        existing = self._vault.read_file(note_path)
        appended = existing + (content or "")
        self._vault.write_note(target, appended, overwrite=True)
        relative = self._vault.to_relative(note_path)
        return NoteManagerResult(
            success=True,
            operation="append_note",
            affected_count=1,
            affected_paths=[relative],
            message=f"Content appended to '{relative}'.",
        )

    def delete_note(
        self,
        target: str | None,
        confirm_destructive: bool,
    ) -> NoteManagerResult:
        """Delete a note from the vault.

        Args:
            target: Vault-relative path to the note.
            confirm_destructive: Must be True to proceed with deletion.

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="delete_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    "delete_note requires a target path. "
                    "Use obsidian_query_vault_tool to find the note path first."
                ),
            )

        if not confirm_destructive:
            return NoteManagerResult(
                success=False,
                operation="delete_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    f"delete_note requires confirm_destructive=True to prevent accidental data loss. "
                    f"Set confirm_destructive=True to permanently delete '{target}'."
                ),
            )

        try:
            path = self._vault.delete_note(target)
            relative = self._vault.to_relative(path)
            return NoteManagerResult(
                success=True,
                operation="delete_note",
                affected_count=1,
                affected_paths=[relative],
                message=f"Note deleted: '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="delete_note",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    def move_note(
        self,
        target: str | None,
        destination: str | None,
        _create_folders: bool,
    ) -> NoteManagerResult:
        """Move a note to a new location in the vault.

        Args:
            target: Vault-relative source path.
            destination: Vault-relative destination path (including filename).
            _create_folders: Unused — VaultManager.move_path always creates parent dirs.

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target or not destination:
            return NoteManagerResult(
                success=False,
                operation="move_note",
                affected_count=0,
                affected_paths=[],
                message=(
                    "move_note requires both target and destination parameters. "
                    "Example: target='Inbox/Draft.md', destination='Projects/Draft.md'"
                ),
            )

        try:
            new_path = self._vault.move_path(target, destination)
            relative = self._vault.to_relative(new_path)
            return NoteManagerResult(
                success=True,
                operation="move_note",
                affected_count=1,
                affected_paths=[relative],
                message=f"Note moved to '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="move_note",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    # -------------------------------------------------------------------------
    # Folder operations
    # -------------------------------------------------------------------------

    def create_folder(
        self,
        target: str | None,
        _create_folders: bool,
    ) -> NoteManagerResult:
        """Create a folder (and any missing parent folders) in the vault.

        Args:
            target: Vault-relative folder path to create.
            _create_folders: Unused — folder creation always uses mkdir(parents=True).

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="create_folder",
                affected_count=0,
                affected_paths=[],
                message=(
                    "create_folder requires a target path. Example: target='Projects/2025/Q1'"
                ),
            )

        path = self._vault.create_folder(target)
        relative = self._vault.to_relative(path)
        return NoteManagerResult(
            success=True,
            operation="create_folder",
            affected_count=1,
            affected_paths=[relative],
            message=f"Folder created at '{relative}'.",
        )

    def delete_folder(
        self,
        target: str | None,
        confirm_destructive: bool,
    ) -> NoteManagerResult:
        """Delete a folder from the vault.

        Args:
            target: Vault-relative folder path to delete.
            confirm_destructive: Must be True for non-empty folders (recursive delete).

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target:
            return NoteManagerResult(
                success=False,
                operation="delete_folder",
                affected_count=0,
                affected_paths=[],
                message=(
                    "delete_folder requires a target path. Example: target='Archive/OldProject'"
                ),
            )

        if not confirm_destructive:
            return NoteManagerResult(
                success=False,
                operation="delete_folder",
                affected_count=0,
                affected_paths=[],
                message=(
                    f"delete_folder requires confirm_destructive=True for non-empty folders. "
                    f"Set confirm_destructive=True to delete '{target}' and all its contents."
                ),
            )

        try:
            path = self._vault.delete_folder(target, recursive=True)
            relative = self._vault.to_relative(path)
            return NoteManagerResult(
                success=True,
                operation="delete_folder",
                affected_count=1,
                affected_paths=[relative],
                message=f"Folder deleted: '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="delete_folder",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    def move_folder(
        self,
        target: str | None,
        destination: str | None,
    ) -> NoteManagerResult:
        """Move a folder to a new location in the vault.

        Args:
            target: Vault-relative source folder path.
            destination: Vault-relative destination path.

        Returns:
            NoteManagerResult describing the outcome.
        """
        if not target or not destination:
            return NoteManagerResult(
                success=False,
                operation="move_folder",
                affected_count=0,
                affected_paths=[],
                message=(
                    "move_folder requires both target and destination parameters. "
                    "Example: target='Inbox', destination='Archive/Inbox-2024'"
                ),
            )

        try:
            new_path = self._vault.move_path(target, destination)
            relative = self._vault.to_relative(new_path)
            return NoteManagerResult(
                success=True,
                operation="move_folder",
                affected_count=1,
                affected_paths=[relative],
                message=f"Folder moved to '{relative}'.",
            )
        except ValueError as exc:
            return NoteManagerResult(
                success=False,
                operation="move_folder",
                affected_count=0,
                affected_paths=[],
                message=str(exc),
            )

    # -------------------------------------------------------------------------
    # Bulk operations
    # -------------------------------------------------------------------------

    def bulk_tag(
        self,
        targets: list[str] | None,
        metadata: dict[str, object] | None,
    ) -> NoteManagerResult:
        """Add or replace tags on multiple notes via frontmatter update.

        Args:
            targets: List of vault-relative note paths.
            metadata: Frontmatter changes to apply to each note (typically {"tags": [...]}).

        Returns:
            NoteManagerResult with partial_success=True if some items failed.
        """
        if not targets:
            return NoteManagerResult(
                success=False,
                operation="bulk_tag",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_tag requires a targets list of note paths. "
                    "Use obsidian_query_vault_tool to find the target paths first."
                ),
            )
        if not metadata:
            return NoteManagerResult(
                success=False,
                operation="bulk_tag",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_tag requires a metadata dict with the changes to apply. "
                    "Example: metadata={'tags': ['reviewed', 'archived']}"
                ),
            )

        succeeded: list[str] = []
        failures: list[BulkOperationFailure] = []

        for note_path in targets:
            try:
                self._vault.update_frontmatter(note_path, metadata)
                succeeded.append(note_path)
            except ValueError as exc:
                failures.append(BulkOperationFailure(path=note_path, reason=str(exc)))

        total = len(targets)
        success_count = len(succeeded)
        has_failures = len(failures) > 0
        partial = has_failures and success_count > 0

        return NoteManagerResult(
            success=success_count > 0,
            operation="bulk_tag",
            affected_count=success_count,
            affected_paths=succeeded,
            message=(
                f"bulk_tag completed: {success_count} of {total} notes updated."
                if not has_failures
                else (
                    f"bulk_tag partially completed: {success_count} of {total} notes updated. "
                    f"{len(failures)} failed."
                )
            ),
            partial_success=partial if has_failures else None,
            failures=failures if failures else None,
        )

    def bulk_move(
        self,
        targets: list[str] | None,
        destination: str | None,
    ) -> NoteManagerResult:
        """Move multiple notes into a destination folder.

        Args:
            targets: List of vault-relative note paths to move.
            destination: Vault-relative destination folder path.

        Returns:
            NoteManagerResult with partial_success=True if some items failed.
        """
        if not targets:
            return NoteManagerResult(
                success=False,
                operation="bulk_move",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_move requires a targets list of note paths. "
                    "Use obsidian_query_vault_tool to find the target paths first."
                ),
            )
        if not destination:
            return NoteManagerResult(
                success=False,
                operation="bulk_move",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_move requires a destination folder path. "
                    "Example: destination='Archive/2024'"
                ),
            )

        succeeded: list[str] = []
        failures: list[BulkOperationFailure] = []

        for note_path in targets:
            from pathlib import Path as _Path

            filename = _Path(note_path).name
            dest_path = f"{destination}/{filename}"
            try:
                new_path = self._vault.move_path(note_path, dest_path)
                succeeded.append(self._vault.to_relative(new_path))
            except ValueError as exc:
                failures.append(BulkOperationFailure(path=note_path, reason=str(exc)))

        total = len(targets)
        success_count = len(succeeded)
        has_failures = len(failures) > 0
        partial = has_failures and success_count > 0

        return NoteManagerResult(
            success=success_count > 0,
            operation="bulk_move",
            affected_count=success_count,
            affected_paths=succeeded,
            message=(
                f"bulk_move completed: {success_count} of {total} notes moved to '{destination}'."
                if not has_failures
                else (
                    f"bulk_move partially completed: {success_count} of {total} notes moved. "
                    f"{len(failures)} failed."
                )
            ),
            partial_success=partial if has_failures else None,
            failures=failures if failures else None,
        )

    def bulk_update_metadata(
        self,
        targets: list[str] | None,
        metadata_changes: dict[str, object] | None,
    ) -> NoteManagerResult:
        """Apply frontmatter changes to multiple notes.

        Args:
            targets: List of vault-relative note paths.
            metadata_changes: Frontmatter key-value pairs to merge into each note.

        Returns:
            NoteManagerResult with partial_success=True if some items failed.
        """
        if not targets:
            return NoteManagerResult(
                success=False,
                operation="bulk_update_metadata",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_update_metadata requires a targets list. "
                    "Use obsidian_query_vault_tool to find target note paths."
                ),
            )
        if not metadata_changes:
            return NoteManagerResult(
                success=False,
                operation="bulk_update_metadata",
                affected_count=0,
                affected_paths=[],
                message=(
                    "bulk_update_metadata requires a metadata_changes dict. "
                    "Example: metadata_changes={'status': 'reviewed', 'reviewed_date': '2025-01-15'}"
                ),
            )

        succeeded: list[str] = []
        failures: list[BulkOperationFailure] = []

        for note_path in targets:
            try:
                self._vault.update_frontmatter(note_path, metadata_changes)
                succeeded.append(note_path)
            except ValueError as exc:
                failures.append(BulkOperationFailure(path=note_path, reason=str(exc)))

        total = len(targets)
        success_count = len(succeeded)
        has_failures = len(failures) > 0
        partial = has_failures and success_count > 0

        return NoteManagerResult(
            success=success_count > 0,
            operation="bulk_update_metadata",
            affected_count=success_count,
            affected_paths=succeeded,
            message=(
                f"bulk_update_metadata completed: {success_count} of {total} notes updated."
                if not has_failures
                else (
                    f"bulk_update_metadata partially completed: {success_count} of {total} updated. "
                    f"{len(failures)} failed."
                )
            ),
            partial_success=partial if has_failures else None,
            failures=failures if failures else None,
        )

    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------

    def dispatch(
        self,
        operation: str,
        target: str | None = None,
        targets: list[str] | None = None,
        content: str | None = None,
        destination: str | None = None,
        metadata: dict[str, object] | None = None,
        metadata_changes: dict[str, object] | None = None,
        confirm_destructive: bool = False,
        create_folders: bool = True,
    ) -> NoteManagerResult:
        """Route an operation string to the appropriate service method.

        Args:
            operation: One of the 11 supported operation literals.
            target: Single-target path (notes and folders).
            targets: Multi-target paths (bulk operations).
            content: Note body content.
            destination: Destination path for move operations.
            metadata: Frontmatter dict for create/bulk_tag operations.
            metadata_changes: Frontmatter changes for bulk_update_metadata.
            confirm_destructive: Safety flag required for delete operations.
            create_folders: Whether to auto-create parent directories.

        Returns:
            NoteManagerResult from the dispatched method.
        """
        if operation == "create_note":
            return self.create_note(target, content, metadata, create_folders)
        if operation == "update_note":
            return self.update_note(target, content)
        if operation == "append_note":
            return self.append_note(target, content)
        if operation == "delete_note":
            return self.delete_note(target, confirm_destructive)
        if operation == "move_note":
            return self.move_note(target, destination, create_folders)
        if operation == "create_folder":
            return self.create_folder(target, create_folders)
        if operation == "delete_folder":
            return self.delete_folder(target, confirm_destructive)
        if operation == "move_folder":
            return self.move_folder(target, destination)
        if operation == "bulk_tag":
            return self.bulk_tag(targets, metadata)
        if operation == "bulk_move":
            return self.bulk_move(targets, destination)
        if operation == "bulk_update_metadata":
            return self.bulk_update_metadata(targets, metadata_changes)

        return NoteManagerResult(
            success=False,
            operation=operation,
            affected_count=0,
            affected_paths=[],
            message=(
                f"Unknown operation: '{operation}'. Valid operations: create_note, update_note, "
                "append_note, delete_note, move_note, create_folder, delete_folder, move_folder, "
                "bulk_tag, bulk_move, bulk_update_metadata."
            ),
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _build_content_with_frontmatter(self, content: str, metadata: dict[str, object]) -> str:
        """Prepend YAML frontmatter to note content.

        Args:
            content: Note body text.
            metadata: Frontmatter key-value pairs.

        Returns:
            Combined string with frontmatter block followed by content.
        """
        frontmatter = self._vault._serialise_frontmatter(metadata)
        return f"{frontmatter}\n{content}"
