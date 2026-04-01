"""Unit tests for obsidian_get_context_tool Pydantic models."""

import pytest

from app.features.obsidian_get_context.obsidian_get_context_models import (
    BacklinkInfo,
    ContextResult,
    NoteContent,
)


@pytest.mark.unit
def test_note_content_defaults() -> None:
    note = NoteContent(path="Projects/Alpha.md", title="Alpha", content="Hello world")
    assert note.metadata is None
    assert note.word_count == 0


@pytest.mark.unit
def test_note_content_with_metadata() -> None:
    note = NoteContent(
        path="Projects/Alpha.md",
        title="Alpha",
        content="Hello world",
        metadata={"tags": ["project"], "status": "active"},
        word_count=2,
    )
    assert note.metadata is not None
    assert note.metadata["tags"] == ["project"]
    assert note.word_count == 2


@pytest.mark.unit
def test_backlink_info_fields() -> None:
    bl = BacklinkInfo(
        note_path="Projects/Beta.md",
        note_title="Beta",
        context="...see [[Alpha]] for details...",
    )
    assert bl.note_path == "Projects/Beta.md"
    assert bl.note_title == "Beta"
    assert "Alpha" in bl.context


@pytest.mark.unit
def test_context_result_defaults() -> None:
    result = ContextResult(
        primary_note=NoteContent(path="a.md", title="A", content="content"),
    )
    assert result.related_notes is None
    assert result.backlinks is None
    assert result.metadata_summary is None
    assert result.token_estimate == 0
    assert result.context_type == ""
    assert result.error is None


@pytest.mark.unit
def test_context_result_json_roundtrip() -> None:
    result = ContextResult(
        primary_note=NoteContent(
            path="Projects/Alpha.md",
            title="Alpha Project",
            content="# Alpha\nMachine learning experiment.",
            metadata={"tags": ["project", "active"]},
            word_count=4,
        ),
        related_notes=[
            NoteContent(path="Projects/Beta.md", title="Beta", content="Old work.", word_count=2)
        ],
        backlinks=[
            BacklinkInfo(
                note_path="Notes/Ref.md",
                note_title="Reference",
                context="...see [[Alpha Project]]...",
            )
        ],
        metadata_summary={"tags": ["project", "active"]},
        token_estimate=150,
        context_type="read_note",
        error=None,
    )
    restored = ContextResult.model_validate_json(result.model_dump_json())
    assert restored.primary_note.path == "Projects/Alpha.md"
    assert restored.primary_note.title == "Alpha Project"
    assert restored.related_notes is not None
    assert restored.related_notes[0].path == "Projects/Beta.md"
    assert restored.backlinks is not None
    assert restored.backlinks[0].note_path == "Notes/Ref.md"
    assert restored.token_estimate == 150
    assert restored.context_type == "read_note"
    assert restored.error is None


@pytest.mark.unit
def test_context_result_with_error() -> None:
    result = ContextResult(
        primary_note=NoteContent(path="", title="error", content="Note not found", word_count=0),
        context_type="read_note",
        error="Note not found at 'Missing.md'.",
    )
    assert result.error is not None
    assert "not found" in result.error
