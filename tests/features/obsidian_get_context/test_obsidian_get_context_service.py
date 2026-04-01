"""Unit tests for GetContextService."""

import datetime
from pathlib import Path

import pytest

from app.features.obsidian_get_context.obsidian_get_context_service import GetContextService
from app.shared.vault.vault_manager import VaultManager


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal vault with tagged notes, daily notes, and backlinks."""
    # Tagged primary note
    (tmp_path / "Projects").mkdir()
    (tmp_path / "Projects" / "Alpha.md").write_text(
        "---\ntags: [project, ml]\n---\n# Alpha Project\nMachine learning experiment.",
        encoding="utf-8",
    )
    # Note sharing tags with Alpha
    (tmp_path / "Projects" / "Beta.md").write_text(
        "---\ntags: [project, archived]\n---\n# Beta Project\nOld Python work.",
        encoding="utf-8",
    )
    # Note without frontmatter
    (tmp_path / "Projects" / "NoFrontmatter.md").write_text(
        "# No Frontmatter\nThis note has no tags.",
        encoding="utf-8",
    )
    # Note that links back to Alpha
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Reference.md").write_text(
        "# Reference\nSee [[Alpha Project]] for the main experiment.\nAlso check [[Alpha]].",
        encoding="utf-8",
    )
    # Daily Notes folder
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    (tmp_path / "Daily Notes").mkdir()
    (tmp_path / "Daily Notes" / f"{today}.md").write_text(
        f"---\ntags: [daily]\n---\n# {today}\nToday's journal entry.",
        encoding="utf-8",
    )
    # Specific past daily note
    (tmp_path / "Daily Notes" / "2025-01-15.md").write_text(
        "---\ntags: [daily]\n---\n# 2025-01-15\nReviewed ML papers.",
        encoding="utf-8",
    )
    # Long note for concise truncation test (201+ words)
    long_content = " ".join([f"word{i}" for i in range(250)])
    (tmp_path / "LongNote.md").write_text(f"# Long Note\n{long_content}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def service(vault_root: Path) -> GetContextService:
    """Return a GetContextService backed by the tmp vault."""
    return GetContextService(VaultManager(str(vault_root)))


# ---------------------------------------------------------------------------
# read_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_note_returns_full_content(vault_root: Path, service: GetContextService) -> None:
    result = service.read_note(
        "Projects/Alpha.md",
        include_metadata=False,
        include_backlinks=False,
        max_related=3,
        concise=False,
    )
    assert result.context_type == "read_note"
    assert result.error is None
    assert "Machine learning experiment" in result.primary_note.content
    assert Path(result.primary_note.path) == Path("Projects/Alpha.md")
    assert result.primary_note.title == "Alpha Project"


@pytest.mark.unit
def test_read_note_concise_truncates_content(vault_root: Path, service: GetContextService) -> None:
    result = service.read_note(
        "LongNote.md", include_metadata=False, include_backlinks=False, max_related=3, concise=True
    )
    assert result.error is None
    words = result.primary_note.content.rstrip("…").split()
    assert len(words) <= 200
    assert result.primary_note.content.endswith("…")


@pytest.mark.unit
def test_read_note_includes_metadata(vault_root: Path, service: GetContextService) -> None:
    result = service.read_note(
        "Projects/Alpha.md",
        include_metadata=True,
        include_backlinks=False,
        max_related=3,
        concise=False,
    )
    assert result.error is None
    assert result.primary_note.metadata is not None
    assert "tags" in result.primary_note.metadata
    assert result.metadata_summary is not None


@pytest.mark.unit
def test_read_note_no_frontmatter_metadata_is_none(
    vault_root: Path, service: GetContextService
) -> None:
    result = service.read_note(
        "Projects/NoFrontmatter.md",
        include_metadata=True,
        include_backlinks=False,
        max_related=3,
        concise=False,
    )
    assert result.error is None
    assert result.primary_note.metadata is None


@pytest.mark.unit
def test_read_note_missing_raises_error(service: GetContextService) -> None:
    result = service.read_note(
        "DoesNotExist.md",
        include_metadata=False,
        include_backlinks=False,
        max_related=3,
        concise=False,
    )
    assert result.error is not None
    assert result.primary_note.title == "error"


@pytest.mark.unit
def test_read_note_none_target_returns_error(service: GetContextService) -> None:
    result = service.read_note(
        None, include_metadata=False, include_backlinks=False, max_related=3, concise=False
    )
    assert result.error is not None
    assert "target" in result.error.lower()


# ---------------------------------------------------------------------------
# read_multiple
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_multiple_first_is_primary(vault_root: Path, service: GetContextService) -> None:
    result = service.read_multiple(
        ["Projects/Alpha.md", "Projects/Beta.md"],
        include_metadata=False,
        concise=False,
    )
    assert result.error is None
    assert Path(result.primary_note.path) == Path("Projects/Alpha.md")
    assert result.related_notes is not None
    assert len(result.related_notes) == 1
    assert Path(result.related_notes[0].path) == Path("Projects/Beta.md")


@pytest.mark.unit
def test_read_multiple_empty_targets_returns_error(service: GetContextService) -> None:
    result = service.read_multiple([], include_metadata=False, concise=False)
    assert result.error is not None
    assert result.primary_note.title == "error"


@pytest.mark.unit
def test_read_multiple_none_targets_returns_error(service: GetContextService) -> None:
    result = service.read_multiple(None, include_metadata=False, concise=False)
    assert result.error is not None


@pytest.mark.unit
def test_read_multiple_skips_missing_notes(vault_root: Path, service: GetContextService) -> None:
    result = service.read_multiple(
        ["Projects/Alpha.md", "DoesNotExist.md"],
        include_metadata=False,
        concise=False,
    )
    assert Path(result.primary_note.path) == Path("Projects/Alpha.md")
    assert result.error is not None
    assert "DoesNotExist.md" in result.error


# ---------------------------------------------------------------------------
# gather_related
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_gather_related_uses_tags(vault_root: Path, service: GetContextService) -> None:
    result = service.gather_related(
        "Projects/Alpha.md", include_metadata=False, max_related=5, concise=False
    )
    assert result.error is None
    assert result.related_notes is not None
    assert len(result.related_notes) >= 1
    paths = [n.path for n in result.related_notes]
    assert any("Beta.md" in p for p in paths)


@pytest.mark.unit
def test_gather_related_no_tags_returns_error(vault_root: Path, service: GetContextService) -> None:
    result = service.gather_related(
        "Projects/NoFrontmatter.md", include_metadata=False, max_related=3, concise=False
    )
    assert result.error is not None
    assert "tags" in result.error.lower()


@pytest.mark.unit
def test_gather_related_none_target_returns_error(service: GetContextService) -> None:
    result = service.gather_related(None, include_metadata=False, max_related=3, concise=False)
    assert result.error is not None


# ---------------------------------------------------------------------------
# daily_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_note_today(vault_root: Path, service: GetContextService) -> None:
    result = service.daily_note("today", include_metadata=False, concise=False)
    assert result.error is None
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    assert today in result.primary_note.path


@pytest.mark.unit
def test_daily_note_specific_date(vault_root: Path, service: GetContextService) -> None:
    result = service.daily_note("2025-01-15", include_metadata=False, concise=False)
    assert result.error is None
    assert "2025-01-15" in result.primary_note.path
    assert "ML papers" in result.primary_note.content


@pytest.mark.unit
def test_daily_note_not_found(service: GetContextService) -> None:
    result = service.daily_note("1900-01-01", include_metadata=False, concise=False)
    assert result.error is not None
    assert "1900-01-01" in result.error
    assert result.primary_note.title == "error"


@pytest.mark.unit
def test_daily_note_none_defaults_to_today(vault_root: Path, service: GetContextService) -> None:
    result = service.daily_note(None, include_metadata=False, concise=False)
    assert result.error is None
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    assert today in result.primary_note.path


# ---------------------------------------------------------------------------
# note_with_backlinks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_note_with_backlinks_finds_links(vault_root: Path, service: GetContextService) -> None:
    result = service.note_with_backlinks(
        "Projects/Alpha.md", include_metadata=False, max_related=10, concise=False
    )
    assert result.error is None
    assert result.backlinks is not None
    assert len(result.backlinks) >= 1
    paths = [bl.note_path for bl in result.backlinks]
    assert any("Reference.md" in p for p in paths)


@pytest.mark.unit
def test_note_with_backlinks_no_links_returns_none(
    vault_root: Path, service: GetContextService
) -> None:
    result = service.note_with_backlinks(
        "Projects/Beta.md", include_metadata=False, max_related=5, concise=False
    )
    assert result.error is None
    assert result.backlinks is None


@pytest.mark.unit
def test_note_with_backlinks_none_target_returns_error(service: GetContextService) -> None:
    result = service.note_with_backlinks(None, include_metadata=False, max_related=3, concise=False)
    assert result.error is not None


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dispatch_unknown_context_type_raises(service: GetContextService) -> None:
    with pytest.raises(ValueError, match="Unknown context_type"):
        service.dispatch("invalid_type")


@pytest.mark.unit
def test_dispatch_routes_read_note(vault_root: Path, service: GetContextService) -> None:
    result = service.dispatch("read_note", target="Projects/Alpha.md")
    assert result.context_type == "read_note"
    assert Path(result.primary_note.path) == Path("Projects/Alpha.md")


@pytest.mark.unit
def test_token_estimate_is_populated(vault_root: Path, service: GetContextService) -> None:
    result = service.read_note(
        "Projects/Alpha.md",
        include_metadata=False,
        include_backlinks=False,
        max_related=3,
        concise=False,
    )
    assert result.token_estimate > 0
