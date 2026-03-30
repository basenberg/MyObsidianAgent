"""Unit tests for obsidian_note_manager_tool."""

from pathlib import Path

import pytest

from app.core.agent.dependencies import AgentDependencies
from app.features.obsidian_note_manager.obsidian_note_manager_models import NoteManagerResult
from app.features.obsidian_note_manager.obsidian_note_manager_tool import obsidian_note_manager_tool


class FakeContext:
    """Minimal RunContext substitute for unit tests — avoids needing a real agent run."""

    def __init__(self, vault_path: str) -> None:
        self.deps = AgentDependencies(vault_path=vault_path, request_id="test-tool-req")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal fake vault for tool-level tests."""
    (tmp_path / "Projects").mkdir()
    (tmp_path / "Projects" / "Alpha.md").write_text(
        "---\ntags: [project, active]\n---\n# Alpha Project\nMachine learning experiment.",
        encoding="utf-8",
    )
    (tmp_path / "Projects" / "Beta.md").write_text(
        "---\ntags: [project, archived]\n---\n# Beta Project\nOld Python work.",
        encoding="utf-8",
    )
    (tmp_path / "Daily").mkdir()
    (tmp_path / "Daily" / "2025-01-15.md").write_text(
        "---\ntags: [daily]\n---\n# 2025-01-15\nReviewed ML papers.",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# My Vault\nWelcome.", encoding="utf-8")
    return tmp_path


@pytest.mark.unit
async def test_create_note_tool_returns_success_json(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="create_note",
        target="Test/NewNote.md",
        content="# New Note\nCreated by tool test.",
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    assert result.operation == "create_note"
    assert len(result.affected_paths) == 1
    assert (vault_root / "Test" / "NewNote.md").exists()


@pytest.mark.unit
async def test_delete_note_tool_without_confirm_returns_failure(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="delete_note",
        target="Projects/Alpha.md",
        confirm_destructive=False,
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert not result.success
    assert "confirm_destructive=True" in result.message
    # File must still exist
    assert (vault_root / "Projects" / "Alpha.md").exists()


@pytest.mark.unit
async def test_delete_note_tool_with_confirm_returns_success(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="delete_note",
        target="Projects/Alpha.md",
        confirm_destructive=True,
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    assert result.operation == "delete_note"
    assert not (vault_root / "Projects" / "Alpha.md").exists()


@pytest.mark.unit
async def test_update_note_tool_replaces_content(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="update_note",
        target="README.md",
        content="# Updated Vault\nNew content here.",
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    content = (vault_root / "README.md").read_text(encoding="utf-8")
    assert "Updated Vault" in content
    assert "New content here" in content


@pytest.mark.unit
async def test_bulk_tag_tool_tags_all_targets(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="bulk_tag",
        targets=["Projects/Alpha.md", "Projects/Beta.md"],
        metadata={"status": "reviewed"},
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    assert result.affected_count == 2
    assert result.failures is None


@pytest.mark.unit
async def test_tool_invalid_vault_returns_failure_json() -> None:
    ctx = FakeContext("/nonexistent/vault/path")
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="create_note",
        target="Test.md",
        content="# Test",
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert not result.success
    assert "does not exist" in result.message.lower() or "not exist" in result.message.lower()


@pytest.mark.unit
async def test_append_note_tool_appends_content(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="append_note",
        target="README.md",
        content="\n## Appended\nNew section.",
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    content = (vault_root / "README.md").read_text(encoding="utf-8")
    assert "Welcome." in content
    assert "Appended" in content


@pytest.mark.unit
async def test_move_note_tool_moves_file(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_note_manager_tool(
        ctx,  # type: ignore[arg-type]
        operation="move_note",
        target="Projects/Alpha.md",
        destination="Archive/Alpha.md",
    )
    result = NoteManagerResult.model_validate_json(raw)
    assert result.success
    assert not (vault_root / "Projects" / "Alpha.md").exists()
    assert (vault_root / "Archive" / "Alpha.md").exists()
