"""Unit tests for obsidian_get_context_tool."""

import datetime
from pathlib import Path

import pytest

from app.core.agent.dependencies import AgentDependencies
from app.features.obsidian_get_context.obsidian_get_context_models import ContextResult
from app.features.obsidian_get_context.obsidian_get_context_tools import obsidian_get_context_tool


class FakeContext:
    """Minimal RunContext substitute for unit tests — avoids needing a real agent run."""

    def __init__(self, vault_path: str) -> None:
        self.deps = AgentDependencies(vault_path=vault_path, request_id="test-req-id")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal vault fixture for tool tests."""
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()

    (tmp_path / "Projects").mkdir()
    (tmp_path / "Projects" / "Alpha.md").write_text(
        "---\ntags: [project, ml]\n---\n# Alpha Project\nMachine learning experiment.",
        encoding="utf-8",
    )
    (tmp_path / "Projects" / "Beta.md").write_text(
        "---\ntags: [project, archived]\n---\n# Beta Project\nOld Python work.",
        encoding="utf-8",
    )
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Reference.md").write_text(
        "# Reference\nSee [[Alpha Project]] for details.",
        encoding="utf-8",
    )
    (tmp_path / "Daily Notes").mkdir()
    (tmp_path / "Daily Notes" / f"{today}.md").write_text(
        f"---\ntags: [daily]\n---\n# {today}\nToday's journal.",
        encoding="utf-8",
    )
    # Long note for concise test
    long_content = " ".join([f"word{i}" for i in range(250)])
    (tmp_path / "LongNote.md").write_text(f"# Long Note\n{long_content}", encoding="utf-8")
    return tmp_path


@pytest.mark.unit
async def test_read_note_tool_returns_json(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="read_note",
        target="Projects/Alpha.md",
    )
    result = ContextResult.model_validate_json(raw)
    assert result.context_type == "read_note"
    assert result.error is None
    assert "Alpha Project" in result.primary_note.title
    assert "Machine learning" in result.primary_note.content


@pytest.mark.unit
async def test_read_note_tool_concise_format(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    detailed_raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="read_note",
        target="LongNote.md",
        response_format="detailed",
    )
    concise_raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="read_note",
        target="LongNote.md",
        response_format="concise",
    )
    detailed_result = ContextResult.model_validate_json(detailed_raw)
    concise_result = ContextResult.model_validate_json(concise_raw)
    assert len(concise_result.primary_note.content) < len(detailed_result.primary_note.content)
    assert concise_result.primary_note.content.endswith("…")


@pytest.mark.unit
async def test_read_multiple_tool_returns_related_notes(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="read_multiple",
        targets=["Projects/Alpha.md", "Projects/Beta.md"],
    )
    result = ContextResult.model_validate_json(raw)
    assert result.context_type == "read_multiple"
    assert result.error is None
    assert Path(result.primary_note.path) == Path("Projects/Alpha.md")
    assert result.related_notes is not None
    assert len(result.related_notes) == 1
    assert "Beta.md" in result.related_notes[0].path


@pytest.mark.unit
async def test_gather_related_tool(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="gather_related",
        target="Projects/Alpha.md",
        max_related=5,
    )
    result = ContextResult.model_validate_json(raw)
    assert result.context_type == "gather_related"
    assert result.related_notes is not None
    assert len(result.related_notes) >= 1


@pytest.mark.unit
async def test_daily_note_tool_today(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="daily_note",
        date="today",
    )
    result = ContextResult.model_validate_json(raw)
    assert result.context_type == "daily_note"
    assert result.error is None
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    assert today in result.primary_note.path


@pytest.mark.unit
async def test_note_with_backlinks_tool(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="note_with_backlinks",
        target="Projects/Alpha.md",
        max_related=10,
    )
    result = ContextResult.model_validate_json(raw)
    assert result.context_type == "note_with_backlinks"
    assert result.error is None
    assert result.backlinks is not None
    assert any("Reference.md" in bl.note_path for bl in result.backlinks)


@pytest.mark.unit
async def test_tool_handles_missing_note_gracefully(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_get_context_tool(
        ctx,  # type: ignore[arg-type]
        context_type="read_note",
        target="DoesNotExist.md",
    )
    result = ContextResult.model_validate_json(raw)
    assert result.error is not None
    assert result.primary_note.title == "error"
