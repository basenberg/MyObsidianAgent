"""Unit tests for obsidian_query_vault_tool."""

from pathlib import Path

import pytest

from app.core.agent.dependencies import AgentDependencies
from app.features.obsidian_query_vault.obsidian_query_vault_models import QueryResult
from app.features.obsidian_query_vault.obsidian_query_vault_tools import obsidian_query_vault_tool


class FakeContext:
    """Minimal RunContext substitute for unit tests — avoids needing a real agent run."""

    def __init__(self, vault_path: str) -> None:
        self.deps = AgentDependencies(vault_path=vault_path, request_id="test-req-id")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Create a minimal fake vault matching test_vault_manager.py fixture structure."""
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
async def test_semantic_search_finds_results(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(
        ctx,  # type: ignore[arg-type]
        query_type="semantic_search",
        query="machine learning",
    )
    result = QueryResult.model_validate_json(raw)
    assert result.query_type == "semantic_search"
    assert len(result.results) >= 1
    assert any("Alpha.md" in r.path for r in result.results)


@pytest.mark.unit
async def test_semantic_search_missing_query_returns_suggestion(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="semantic_search", query=None)  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.total_found == 0
    assert result.suggestion is not None
    assert result.truncated is False


@pytest.mark.unit
async def test_list_structure_root(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="list_structure", path="")  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.query_type == "list_structure"
    assert len(result.results) >= 1


@pytest.mark.unit
async def test_list_structure_subfolder(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="list_structure", path="Projects")  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert len(result.results) == 2
    assert any("Alpha.md" in r.path for r in result.results)
    assert any("Beta.md" in r.path for r in result.results)


@pytest.mark.unit
async def test_recent_changes_returns_notes(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="recent_changes", limit=5)  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.query_type == "recent_changes"
    assert len(result.results) >= 1


@pytest.mark.unit
async def test_find_related_missing_reference_returns_suggestion(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="find_related", reference_note=None)  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.total_found == 0
    assert result.suggestion is not None


@pytest.mark.unit
async def test_find_related_nonexistent_note_returns_suggestion(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(
        ctx,  # type: ignore[arg-type]
        query_type="find_related",
        reference_note="DoesNotExist.md",
    )
    result = QueryResult.model_validate_json(raw)
    assert result.total_found == 0
    assert result.suggestion is not None


@pytest.mark.unit
async def test_search_by_metadata_missing_filters_returns_suggestion(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="search_by_metadata", filters=None)  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.total_found == 0
    assert result.suggestion is not None


@pytest.mark.unit
async def test_search_by_metadata_tags_filter(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(
        ctx,  # type: ignore[arg-type]
        query_type="search_by_metadata",
        filters={"tags": ["project"]},
    )
    result = QueryResult.model_validate_json(raw)
    assert len(result.results) == 2
    paths = [r.path for r in result.results]
    assert any("Alpha.md" in p for p in paths)
    assert any("Beta.md" in p for p in paths)


@pytest.mark.unit
async def test_detailed_format_populates_excerpt_and_modified(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(
        ctx,  # type: ignore[arg-type]
        query_type="semantic_search",
        query="machine learning",
        response_format="detailed",
    )
    result = QueryResult.model_validate_json(raw)
    assert len(result.results) >= 1
    note = result.results[0]
    assert note.excerpt is not None
    assert note.modified is not None


@pytest.mark.unit
async def test_concise_format_metadata_all_none(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(
        ctx,  # type: ignore[arg-type]
        query_type="recent_changes",
        response_format="concise",
    )
    result = QueryResult.model_validate_json(raw)
    assert len(result.results) >= 1
    note = result.results[0]
    assert note.excerpt is None
    assert note.tags is None
    assert note.modified is None


@pytest.mark.unit
async def test_invalid_vault_path_returns_suggestion_not_exception() -> None:
    ctx = FakeContext("/nonexistent/vault/path/that/does/not/exist")
    raw = await obsidian_query_vault_tool(ctx, query_type="recent_changes")  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    assert result.total_found == 0
    assert result.suggestion is not None
    assert "VAULT_PATH" in result.suggestion


@pytest.mark.unit
async def test_limit_clamped_to_50(vault_root: Path) -> None:
    ctx = FakeContext(str(vault_root))
    raw = await obsidian_query_vault_tool(ctx, query_type="recent_changes", limit=999)  # type: ignore[arg-type]
    result = QueryResult.model_validate_json(raw)
    # Should complete without error — limit was silently clamped to 50
    assert result.query_type == "recent_changes"
    assert isinstance(result.results, list)
