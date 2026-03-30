"""Unit tests for obsidian_note_manager_tool Pydantic models."""

import pytest

from app.features.obsidian_note_manager.obsidian_note_manager_models import (
    BulkOperationFailure,
    NoteManagerResult,
)


@pytest.mark.unit
def test_bulk_operation_failure_fields() -> None:
    f = BulkOperationFailure(path="Projects/Alpha.md", reason="File not found")
    assert f.path == "Projects/Alpha.md"
    assert f.reason == "File not found"


@pytest.mark.unit
def test_note_manager_result_success_defaults() -> None:
    result = NoteManagerResult(
        success=True,
        operation="create_note",
        affected_count=1,
        affected_paths=["Projects/Alpha.md"],
        message="Note created.",
    )
    assert result.success
    assert result.warnings is None
    assert result.partial_success is None
    assert result.failures is None


@pytest.mark.unit
def test_note_manager_result_json_roundtrip() -> None:
    result = NoteManagerResult(
        success=True,
        operation="bulk_tag",
        affected_count=2,
        affected_paths=["A.md", "B.md"],
        message="Done.",
        partial_success=True,
        failures=[BulkOperationFailure(path="C.md", reason="not found")],
    )
    restored = NoteManagerResult.model_validate_json(result.model_dump_json())
    assert restored.affected_count == 2
    assert restored.failures is not None
    assert restored.failures[0].path == "C.md"


@pytest.mark.unit
def test_note_manager_result_failure_defaults() -> None:
    result = NoteManagerResult(
        success=False,
        operation="delete_note",
        affected_count=0,
        affected_paths=[],
        message="confirm_destructive=True required.",
    )
    assert not result.success
    assert result.affected_paths == []
