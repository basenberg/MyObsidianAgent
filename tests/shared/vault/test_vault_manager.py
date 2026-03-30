"""Unit tests for VaultManager file system abstraction."""

import time
from pathlib import Path

import pytest

from app.shared.vault.vault_manager import VaultManager


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal fake Obsidian vault for testing."""
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
def test_init_valid(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    assert vm._root == vault_root


@pytest.mark.unit
def test_init_invalid_path() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        VaultManager("/nonexistent/path/that/does/not/exist")


@pytest.mark.unit
def test_list_markdown_files_recursive(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    files = vm.list_markdown_files(recursive=True)
    names = [f.name for f in files]
    assert "Alpha.md" in names
    assert "Beta.md" in names
    assert "2025-01-15.md" in names
    assert "README.md" in names


@pytest.mark.unit
def test_list_markdown_files_nonrecursive(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    files = vm.list_markdown_files(folder="Projects", recursive=False)
    assert len(files) == 2
    names = [f.name for f in files]
    assert "Alpha.md" in names
    assert "Beta.md" in names


@pytest.mark.unit
def test_list_markdown_files_missing_folder(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    with pytest.raises(ValueError, match="Folder not found"):
        vm.list_markdown_files(folder="NonExistentFolder")


@pytest.mark.unit
def test_search_content_finds_match(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    results = vm.search_content("machine learning")
    paths = [r[0].name for r in results]
    assert "Alpha.md" in paths


@pytest.mark.unit
def test_search_content_case_insensitive(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    results = vm.search_content("MACHINE LEARNING")
    assert len(results) >= 1


@pytest.mark.unit
def test_search_content_no_match(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    results = vm.search_content("quantum entanglement xyzzy")
    assert results == []


@pytest.mark.unit
def test_get_recent_files(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    recent = vm.get_recent_files(limit=2)
    assert len(recent) == 2
    assert all(f.suffix == ".md" for f in recent)


@pytest.mark.unit
def test_get_recent_files_sorted_newest_first(vault_root: Path) -> None:
    """Verify files are sorted by mtime descending."""
    older = vault_root / "older.md"
    newer = vault_root / "newer.md"
    older.write_text("# Older", encoding="utf-8")
    time.sleep(0.05)
    newer.write_text("# Newer", encoding="utf-8")
    vm = VaultManager(str(vault_root))
    recent = vm.get_recent_files(limit=2)
    assert recent[0].name == "newer.md"


@pytest.mark.unit
def test_parse_frontmatter_inline_list(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    fm = vm.parse_frontmatter(vault_root / "Projects" / "Alpha.md")
    assert "tags" in fm
    tags = fm["tags"]
    assert isinstance(tags, list)
    assert "project" in tags
    assert "active" in tags


@pytest.mark.unit
def test_parse_frontmatter_no_frontmatter(vault_root: Path) -> None:
    no_fm = vault_root / "plain.md"
    no_fm.write_text("# Plain\nNo frontmatter here.", encoding="utf-8")
    vm = VaultManager(str(vault_root))
    assert vm.parse_frontmatter(no_fm) == {}


@pytest.mark.unit
def test_parse_frontmatter_block_list(vault_root: Path) -> None:
    note = vault_root / "block_list.md"
    note.write_text(
        "---\ntags:\n- alpha\n- beta\n---\n# Block List Note",
        encoding="utf-8",
    )
    vm = VaultManager(str(vault_root))
    fm = vm.parse_frontmatter(note)
    assert "tags" in fm
    assert "alpha" in fm["tags"]
    assert "beta" in fm["tags"]


@pytest.mark.unit
def test_get_title_from_h1(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    assert vm.get_title(vault_root / "Projects" / "Alpha.md") == "Alpha Project"


@pytest.mark.unit
def test_get_title_fallback_stem(vault_root: Path) -> None:
    no_h1 = vault_root / "notitle.md"
    no_h1.write_text("Just content without any heading.", encoding="utf-8")
    vm = VaultManager(str(vault_root))
    assert vm.get_title(no_h1) == "notitle"


@pytest.mark.unit
def test_find_related_by_tags(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    ref = vault_root / "Projects" / "Alpha.md"
    related = vm.find_related_by_tags(ref, limit=5)
    related_names = [r[0].name for r in related]
    # Beta.md shares "project" tag with Alpha.md
    assert "Beta.md" in related_names


@pytest.mark.unit
def test_get_modified_iso_format(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    iso = vm.get_modified_iso(vault_root / "README.md")
    # Must match YYYY-MM-DDTHH:MM:SSZ
    assert len(iso) == 20
    assert iso[4] == "-"
    assert iso[7] == "-"
    assert iso[10] == "T"
    assert iso[-1] == "Z"


@pytest.mark.unit
def test_to_relative(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    abs_path = vault_root / "Projects" / "Alpha.md"
    rel = vm.to_relative(abs_path)
    assert "Alpha.md" in rel
    assert str(vault_root) not in rel


@pytest.mark.unit
def test_get_note_path(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    result = vm.get_note_path("Projects/Alpha.md")
    assert result == vault_root / "Projects" / "Alpha.md"


# ---------------------------------------------------------------------------
# Write operation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_note_creates_file(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    path = vm.write_note("NewNote.md", "# New Note\nHello world.")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "# New Note\nHello world."


@pytest.mark.unit
def test_write_note_creates_parent_dirs(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    path = vm.write_note("Deep/Nested/Note.md", "# Deep")
    assert path.exists()
    assert (vault_root / "Deep" / "Nested").is_dir()


@pytest.mark.unit
def test_write_note_overwrite_true_replaces_content(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.write_note("Replace.md", "original")
    vm.write_note("Replace.md", "replaced", overwrite=True)
    assert (vault_root / "Replace.md").read_text(encoding="utf-8") == "replaced"


@pytest.mark.unit
def test_write_note_overwrite_false_raises(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.write_note("Existing.md", "original")
    with pytest.raises(ValueError, match="already exists"):
        vm.write_note("Existing.md", "new content")


@pytest.mark.unit
def test_delete_note_removes_file(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    target = vault_root / "Projects" / "Alpha.md"
    assert target.exists()
    result = vm.delete_note("Projects/Alpha.md")
    assert not target.exists()
    assert result == target


@pytest.mark.unit
def test_delete_note_missing_raises(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    with pytest.raises(ValueError, match="not found"):
        vm.delete_note("Projects/DoesNotExist.md")


@pytest.mark.unit
def test_move_path_moves_file(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.move_path("Projects/Alpha.md", "Archive/Alpha.md")
    assert not (vault_root / "Projects" / "Alpha.md").exists()
    assert (vault_root / "Archive" / "Alpha.md").exists()


@pytest.mark.unit
def test_move_path_creates_parent_dirs(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.move_path("README.md", "Deep/Path/README.md")
    assert (vault_root / "Deep" / "Path" / "README.md").exists()


@pytest.mark.unit
def test_move_path_missing_source_raises(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    with pytest.raises(ValueError, match="Source not found"):
        vm.move_path("NoSuchFile.md", "Somewhere/NoSuchFile.md")


@pytest.mark.unit
def test_create_folder_creates_nested(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    result = vm.create_folder("NewFolder/SubFolder")
    assert result.is_dir()
    assert (vault_root / "NewFolder" / "SubFolder").is_dir()


@pytest.mark.unit
def test_create_folder_idempotent(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.create_folder("Projects")  # already exists — should not raise
    assert (vault_root / "Projects").is_dir()


@pytest.mark.unit
def test_delete_folder_non_recursive_nonempty_raises(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    with pytest.raises(ValueError, match="not empty"):
        vm.delete_folder("Projects")


@pytest.mark.unit
def test_delete_folder_recursive(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.delete_folder("Projects", recursive=True)
    assert not (vault_root / "Projects").exists()


@pytest.mark.unit
def test_delete_folder_empty_no_recursive(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    (vault_root / "EmptyFolder").mkdir()
    vm.delete_folder("EmptyFolder")
    assert not (vault_root / "EmptyFolder").exists()


@pytest.mark.unit
def test_delete_folder_missing_raises(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    with pytest.raises(ValueError, match="Folder not found"):
        vm.delete_folder("DoesNotExist")


@pytest.mark.unit
def test_update_frontmatter_merges_keys(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.update_frontmatter("Projects/Alpha.md", {"status": "reviewed"})
    fm = vm.parse_frontmatter(vault_root / "Projects" / "Alpha.md")
    assert fm.get("status") == "reviewed"
    # Existing tags must be preserved
    assert "project" in fm.get("tags", [])


@pytest.mark.unit
def test_update_frontmatter_preserves_body(vault_root: Path) -> None:
    vm = VaultManager(str(vault_root))
    vm.update_frontmatter("Projects/Alpha.md", {"status": "done"})
    content = (vault_root / "Projects" / "Alpha.md").read_text(encoding="utf-8")
    assert "Alpha Project" in content
    assert "Machine learning experiment" in content


@pytest.mark.unit
def test_update_frontmatter_no_existing_frontmatter(vault_root: Path) -> None:
    no_fm = vault_root / "plain.md"
    no_fm.write_text("# Plain Note\nBody text here.", encoding="utf-8")
    vm = VaultManager(str(vault_root))
    vm.update_frontmatter("plain.md", {"tags": ["new"], "status": "active"})
    fm = vm.parse_frontmatter(no_fm)
    assert "status" in fm
    # Body must still be present
    content = no_fm.read_text(encoding="utf-8")
    assert "Body text here" in content
