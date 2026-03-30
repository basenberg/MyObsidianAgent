"""Unit tests for NoteManagerService."""

from pathlib import Path

import pytest

from app.features.obsidian_note_manager.obsidian_note_manager_service import NoteManagerService
from app.shared.vault.vault_manager import VaultManager


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal fake vault for service tests."""
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


@pytest.fixture
def service(vault_root: Path) -> NoteManagerService:
    """Return a NoteManagerService backed by the tmp vault."""
    return NoteManagerService(VaultManager(str(vault_root)))


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_note_creates_file_with_content(
    vault_root: Path, service: NoteManagerService
) -> None:
    result = service.create_note("NewNote.md", "# Hello\nWorld.", None, True)
    assert result.success
    assert result.operation == "create_note"
    assert len(result.affected_paths) == 1
    assert (vault_root / "NewNote.md").read_text(encoding="utf-8") == "# Hello\nWorld."


@pytest.mark.unit
def test_create_note_with_metadata_writes_frontmatter(
    vault_root: Path, service: NoteManagerService
) -> None:
    result = service.create_note(
        "Tagged.md",
        "# Tagged Note",
        {"tags": ["test", "new"], "status": "draft"},
        True,
    )
    assert result.success
    content = (vault_root / "Tagged.md").read_text(encoding="utf-8")
    assert "tags: [test, new]" in content
    assert "status: draft" in content
    assert "# Tagged Note" in content


@pytest.mark.unit
def test_create_note_missing_target_returns_failure(service: NoteManagerService) -> None:
    result = service.create_note(None, "content", None, True)
    assert not result.success
    assert "target" in result.message.lower()


@pytest.mark.unit
def test_create_note_existing_file_returns_failure(service: NoteManagerService) -> None:
    result = service.create_note("Projects/Alpha.md", "new content", None, True)
    assert not result.success
    assert "already exists" in result.message


# ---------------------------------------------------------------------------
# update_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_update_note_replaces_content(vault_root: Path, service: NoteManagerService) -> None:
    result = service.update_note("Projects/Alpha.md", "# Updated\nNew content.")
    assert result.success
    content = (vault_root / "Projects" / "Alpha.md").read_text(encoding="utf-8")
    assert content == "# Updated\nNew content."


@pytest.mark.unit
def test_update_note_missing_target_returns_failure(service: NoteManagerService) -> None:
    result = service.update_note(None, "content")
    assert not result.success


# ---------------------------------------------------------------------------
# append_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_append_note_adds_to_existing(vault_root: Path, service: NoteManagerService) -> None:
    result = service.append_note("README.md", "\n## Appended Section\nNew text.")
    assert result.success
    content = (vault_root / "README.md").read_text(encoding="utf-8")
    assert "Welcome." in content
    assert "Appended Section" in content


@pytest.mark.unit
def test_append_note_missing_note_returns_failure(service: NoteManagerService) -> None:
    result = service.append_note("DoesNotExist.md", "text")
    assert not result.success
    assert "not found" in result.message.lower()


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delete_note_without_confirm_returns_failure(service: NoteManagerService) -> None:
    result = service.delete_note("Projects/Alpha.md", confirm_destructive=False)
    assert not result.success
    assert "confirm_destructive=True" in result.message


@pytest.mark.unit
def test_delete_note_with_confirm_removes_file(
    vault_root: Path, service: NoteManagerService
) -> None:
    result = service.delete_note("Projects/Alpha.md", confirm_destructive=True)
    assert result.success
    assert not (vault_root / "Projects" / "Alpha.md").exists()


@pytest.mark.unit
def test_delete_note_missing_file_returns_failure(service: NoteManagerService) -> None:
    result = service.delete_note("NoSuch.md", confirm_destructive=True)
    assert not result.success
    assert "not found" in result.message.lower()


# ---------------------------------------------------------------------------
# move_note
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_move_note_moves_to_destination(vault_root: Path, service: NoteManagerService) -> None:
    result = service.move_note("Projects/Alpha.md", "Archive/Alpha.md", True)
    assert result.success
    assert not (vault_root / "Projects" / "Alpha.md").exists()
    assert (vault_root / "Archive" / "Alpha.md").exists()


@pytest.mark.unit
def test_move_note_missing_target_returns_failure(service: NoteManagerService) -> None:
    result = service.move_note(None, "Archive/note.md", True)
    assert not result.success


# ---------------------------------------------------------------------------
# create_folder
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_folder_creates_directory(vault_root: Path, service: NoteManagerService) -> None:
    result = service.create_folder("NewFolder/Sub", True)
    assert result.success
    assert (vault_root / "NewFolder" / "Sub").is_dir()


@pytest.mark.unit
def test_create_folder_missing_target_returns_failure(service: NoteManagerService) -> None:
    result = service.create_folder(None, True)
    assert not result.success


# ---------------------------------------------------------------------------
# delete_folder
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delete_folder_without_confirm_returns_failure(service: NoteManagerService) -> None:
    result = service.delete_folder("Projects", confirm_destructive=False)
    assert not result.success
    assert "confirm_destructive=True" in result.message


@pytest.mark.unit
def test_delete_folder_with_confirm_removes_folder(
    vault_root: Path, service: NoteManagerService
) -> None:
    result = service.delete_folder("Projects", confirm_destructive=True)
    assert result.success
    assert not (vault_root / "Projects").exists()


# ---------------------------------------------------------------------------
# bulk_tag
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bulk_tag_updates_all_notes(vault_root: Path, service: NoteManagerService) -> None:
    result = service.bulk_tag(
        ["Projects/Alpha.md", "Projects/Beta.md"],
        {"status": "reviewed"},
    )
    assert result.success
    assert result.affected_count == 2
    assert result.failures is None
    for note in ["Projects/Alpha.md", "Projects/Beta.md"]:
        fm = VaultManager(str(vault_root)).parse_frontmatter(vault_root / note)
        assert fm.get("status") == "reviewed"


@pytest.mark.unit
def test_bulk_tag_partial_failure_reports_failures(service: NoteManagerService) -> None:
    result = service.bulk_tag(
        ["Projects/Alpha.md", "DoesNotExist.md"],
        {"status": "reviewed"},
    )
    assert result.success  # at least one succeeded
    assert result.partial_success is True
    assert result.failures is not None
    assert len(result.failures) == 1
    assert result.failures[0].path == "DoesNotExist.md"


@pytest.mark.unit
def test_bulk_tag_missing_targets_returns_failure(service: NoteManagerService) -> None:
    result = service.bulk_tag(None, {"status": "done"})
    assert not result.success


@pytest.mark.unit
def test_bulk_tag_missing_metadata_returns_failure(service: NoteManagerService) -> None:
    result = service.bulk_tag(["Projects/Alpha.md"], None)
    assert not result.success


# ---------------------------------------------------------------------------
# bulk_move
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bulk_move_moves_all_targets(vault_root: Path, service: NoteManagerService) -> None:
    result = service.bulk_move(
        ["Projects/Alpha.md", "Projects/Beta.md"],
        "Archive",
    )
    assert result.success
    assert result.affected_count == 2
    assert (vault_root / "Archive" / "Alpha.md").exists()
    assert (vault_root / "Archive" / "Beta.md").exists()


# ---------------------------------------------------------------------------
# bulk_update_metadata
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bulk_update_metadata_updates_notes(vault_root: Path, service: NoteManagerService) -> None:
    result = service.bulk_update_metadata(
        ["Projects/Alpha.md", "Projects/Beta.md"],
        {"reviewed": "true"},
    )
    assert result.success
    assert result.affected_count == 2


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dispatch_unknown_operation_returns_failure(service: NoteManagerService) -> None:
    result = service.dispatch("nonexistent_op")
    assert not result.success
    assert "Unknown operation" in result.message


@pytest.mark.unit
def test_dispatch_routes_to_create_note(vault_root: Path, service: NoteManagerService) -> None:
    result = service.dispatch("create_note", target="Dispatched.md", content="# Dispatched")
    assert result.success
    assert (vault_root / "Dispatched.md").exists()
