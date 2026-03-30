"""Pydantic models for obsidian_note_manager_tool responses."""

from pydantic import BaseModel


class BulkOperationFailure(BaseModel):
    """Details of a single failed item within a bulk operation.

    Attributes:
        path: Vault-relative path of the note or folder that failed.
        reason: Human-readable error message explaining why the item failed.
    """

    path: str
    reason: str


class NoteManagerResult(BaseModel):
    """Response model for obsidian_note_manager_tool.

    Attributes:
        success: True if the operation completed (fully or partially).
        operation: The operation that was executed (for agent reference).
        affected_count: Number of notes/folders successfully modified.
        affected_paths: Vault-relative paths of items that were modified.
        message: Human-readable summary of the result.
        warnings: Non-fatal issues encountered during the operation.
        partial_success: True for bulk ops where some items succeeded and some failed.
        failures: Per-item failure details for bulk operations.
    """

    success: bool
    operation: str
    affected_count: int
    affected_paths: list[str]
    message: str
    warnings: list[str] | None = None
    partial_success: bool | None = None
    failures: list[BulkOperationFailure] | None = None
