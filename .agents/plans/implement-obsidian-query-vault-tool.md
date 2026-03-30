# Feature: implement-obsidian-query-vault-tool

Validate codebase patterns and read all referenced files before implementing. Do not skip the reads.
Pay special attention to existing import paths — get them right the first time.

## Feature Description

Add `obsidian_query_vault_tool` — the first Pydantic AI tool on `vault_agent`. Enables vault discovery
and search: keyword search, folder listing, related-note discovery, metadata filtering, recent changes.
Read-only. Establishes the canonical pattern all future tools will mirror.

## User Story

As an Obsidian user chatting with Paddy
I want to ask "find my notes about machine learning" or "what did I change this week"
So that Paddy searches my actual vault instead of hallucinating answers

## Feature Metadata

**Type**: New Capability (first tool — sets the pattern)
**Complexity**: Medium
**Systems**: `app/core/agent/`, `app/features/obsidian_query_vault/`, `app/shared/vault/`
**Dependencies**: stdlib only (pathlib, re, time) — no new packages needed

---

## CONTEXT REFERENCES

### Read These Files Before Implementing

- `app/core/agent/agent.py` — vault_agent singleton; update `instructions=` in Task 9
- `app/core/agent/dependencies.py` — AgentDependencies dataclass; add `vault_path` in Task 2
- `app/core/config.py` (lines 18–60) — Settings class; add `vault_path` in Task 1
- `app/features/chat/routes.py` (lines 148–152) — AgentDependencies construction; update in Task 10
- `app/main.py` (lines 26–27) — import location for tool_registry; update in Task 8
- `app/core/logging.py` (lines 109–145) — `get_logger(__name__)` pattern to mirror in all new files
- `pyproject.toml` — ruff rules (PTH, ANN), asyncio_mode="auto", Python 3.12, mypy+pyright strict,
  per-file-ignores (tests ignore ANN/S101, `__init__.py` ignores F401)
- `.agents/reference/adding_tools_guide.md` — 7-section agent docstring format; required for tool

### New Files to Create

```
app/core/agent/tool_registry.py
app/features/obsidian_query_vault/__init__.py
app/features/obsidian_query_vault/obsidian_query_vault_models.py
app/features/obsidian_query_vault/obsidian_query_vault_tools.py
app/shared/vault/__init__.py
app/shared/vault/vault_manager.py
app/shared/vault/vault_models.py
tests/features/obsidian_query_vault/__init__.py
tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py
tests/shared/vault/__init__.py
tests/shared/vault/test_vault_manager.py
```

### Existing Files to Modify

```
app/core/config.py              — add vault_path field
app/core/agent/dependencies.py  — add vault_path field
app/core/agent/agent.py         — update instructions system prompt
app/main.py                     — add tool_registry import
app/features/chat/routes.py     — pass vault_path to AgentDependencies
```

### Documentation

- https://ai.pydantic.dev/tools/ — `@agent.tool`, `RunContext`, schema auto-generation from type hints
  and Google docstrings. Read the "Schema generation" and "Registering tools" sections.

### Key Patterns

**Tool registration — side-effect import pattern:**
```python
# tools.py: @vault_agent.tool fires at module import time (side effect)
from app.core.agent.agent import vault_agent
@vault_agent.tool
async def obsidian_query_vault_tool(ctx: RunContext[AgentDependencies], ...) -> str: ...

# tool_registry.py: importing this file triggers the decorator above
import app.features.obsidian_query_vault.obsidian_query_vault_tools  # noqa: F401

# main.py: one import registers all tools
import app.core.agent.tool_registry  # noqa: F401
```

**Tool return type — always `str` (JSON), NOT the Pydantic model directly:**
Pydantic AI flattens a single BaseModel parameter into the tool's JSON schema, merging its fields with
the tool's own parameters. Return `result.model_dump_json()` to avoid this entirely.

**Logging (keyword args only — never f-strings in log calls):**
```python
logger = get_logger(__name__)
logger.info("vault.query.tool_started", query_type=query_type, request_id=ctx.deps.request_id)
logger.info("vault.query.tool_completed", result_count=len(results), duration_ms=elapsed)
logger.exception("vault.query.tool_failed", fix_suggestion="Check VAULT_PATH env var")
```

**Critical constraints from pyproject.toml:**
- ruff PTH: pathlib everywhere — `path.read_text()`, `base.glob()`. `os.path.*` and `open()` fail the build
- ruff ANN: all public function signatures need return type annotations
- ruff SLF001: accessing private `vault._root` from outside the class requires `# noqa: SLF001`
- `asyncio_mode = "auto"`: do NOT add `@pytest.mark.asyncio` — causes a double-marking warning
- mypy/pyright strict: no bare `Any` without explicit justification in an inline comment

---

## STEP-BY-STEP TASKS

Execute in dependency order. Validate each task before moving to the next.

---

### TASK 1 — UPDATE `app/core/config.py`

- **ADD** `vault_path: str = "/vault"` to Settings class after the `database_url` field
- **ADD** inline comment: `# Override via VAULT_PATH env var for local dev without Docker`
- **GOTCHA**: This must be a simple scalar field like the existing ones — no validator needed
- **VALIDATE**: `uv run python -c "from app.core.config import get_settings; print(get_settings().vault_path)"`

---

### TASK 2 — UPDATE `app/core/agent/dependencies.py`

- **ADD** `vault_path: str = "/vault"` to AgentDependencies after `request_id`
- **KEEP** as `@dataclass` — do not convert to Pydantic BaseModel
- **VALIDATE**: `uv run python -c "from app.core.agent.dependencies import AgentDependencies; print(AgentDependencies().vault_path)"`

---

### TASK 3 — CREATE `app/shared/vault/__init__.py`

- **CREATE** with module docstring: `"""Shared vault file system abstraction — used by all vault tools."""`
- **VALIDATE**: `uv run python -c "import app.shared.vault"`

---

### TASK 4 — CREATE `app/shared/vault/vault_models.py`

Two Pydantic `BaseModel` classes (no logic — data only):

`VaultNote(path: str, title: str, tags: list[str] = [], modified_iso: str = "", size_bytes: int = 0)`
`VaultFolder(path: str, file_count: int = 0, subfolder_count: int = 0)`

- **VALIDATE**: `uv run python -c "from app.shared.vault.vault_models import VaultNote, VaultFolder; print('ok')"`

---

### TASK 5 — CREATE `app/shared/vault/vault_manager.py`

`VaultManager` class — all vault filesystem operations. Instantiate per-request with
`VaultManager(ctx.deps.vault_path)`. Raises `ValueError` with actionable message if vault_path
doesn't exist or isn't a directory.

**Public interface:**
```python
def __init__(self, vault_path: str) -> None
def list_markdown_files(self, folder: str = "", recursive: bool = True) -> list[Path]
def list_folders(self, folder: str = "") -> list[Path]
def get_recent_files(self, limit: int = 10) -> list[Path]
def read_file(self, path: Path) -> str
def search_content(self, query: str, limit: int = 10) -> list[tuple[Path, str]]
def find_related_by_tags(self, reference: Path, limit: int = 10) -> list[tuple[Path, int]]
def parse_frontmatter(self, path: Path) -> dict[str, Any]
def get_title(self, path: Path) -> str
def get_modified_iso(self, path: Path) -> str
```

**Implementation notes:**
- `self._root = Path(vault_path)` — check `.exists()` and `.is_dir()` in `__init__`, raise `ValueError`
  with message: `"Vault path does not exist: '{vault_path}'. Set VAULT_PATH env var."`
- `list_markdown_files`: `base.glob("**/*.md")` if recursive else `base.glob("*.md")`. Raise `ValueError`
  if folder doesn't exist: `"Folder not found: '{folder}'."`
- `list_folders`: `[p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")]`
- `get_recent_files`: `sorted(self._root.glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]`
- `search_content`: iterate all `*.md`, `query.lower() in content.lower()`, extract 200-char excerpt around
  first match. Wrap `path.read_text(encoding="utf-8")` in try/except OSError and skip on failure.
- `parse_frontmatter`: check file starts with `---`, find closing `\n---`, parse lines between them.
  Handle inline lists `[a, b, c]` and block lists (`- item` lines). Return `{}` if no frontmatter or
  OSError. **Do not import yaml** — it's not in pyproject.toml.
- `find_related_by_tags`: get ref tags via `parse_frontmatter`, scan all `.md` files, score by tag overlap,
  return sorted descending. Return `[]` if ref has no tags.
- `get_title`: read file, return first line starting with `# ` (strip the `# `), fallback to `path.stem`
- `get_modified_iso`: `time.gmtime(path.stat().st_mtime)` → format as `"YYYY-MM-DDTHH:MM:SSZ"` using
  `time` stdlib (no `datetime` import needed)
- Private helpers allowed: `_to_relative(path) -> str`, `_extract_excerpt(content, query) -> str`

**Actionable error messages** — format so the agent knows exactly what to do next:
- Init: `"Vault path does not exist: '{vault_path}'. Set VAULT_PATH env var to the correct path."`
- Missing folder: `"Folder not found: '{folder}'. Use list_markdown_files(folder='') to see top-level structure."`
- Missing note: `"Note not found: '{rel_path}'. Use obsidian_query_vault_tool to find available notes."`

**Required imports**: `from __future__ import annotations`, `import re`, `import time`,
`from pathlib import Path`, `from typing import Any`, `from app.core.logging import get_logger`

- **GOTCHA**: No `os.path` anywhere — ruff PTH fails the build. Use `Path.read_text()`, not `open()`.
- **VALIDATE**: `uv run python -c "from app.shared.vault.vault_manager import VaultManager; print('ok')"`

---

### TASK 6 — CREATE `app/features/obsidian_query_vault/__init__.py`

- **CREATE** with docstring: `"""obsidian_query_vault — vault discovery and search feature slice."""`
- **VALIDATE**: `uv run python -c "import app.features.obsidian_query_vault"`

---

### TASK 7 — CREATE `app/features/obsidian_query_vault/obsidian_query_vault_models.py`

```python
class NoteInfo(BaseModel):
    path: str
    title: str
    relevance: float = 1.0
    excerpt: str | None = None    # detailed mode only
    tags: list[str] | None = None # detailed mode only
    modified: str | None = None   # detailed mode only

class QueryResult(BaseModel):
    results: list[NoteInfo]
    total_found: int
    truncated: bool
    query_type: str
    suggestion: str | None = None  # guidance when empty or truncated
```

- **VALIDATE**: `uv run python -c "from app.features.obsidian_query_vault.obsidian_query_vault_models import QueryResult, NoteInfo; print('ok')"`

---

### TASK 8 — CREATE `app/features/obsidian_query_vault/obsidian_query_vault_tools.py`

**Signature:**
```python
@vault_agent.tool
async def obsidian_query_vault_tool(
    ctx: RunContext[AgentDependencies],
    query_type: Literal["semantic_search", "list_structure", "find_related",
                        "search_by_metadata", "recent_changes"],
    query: str | None = None,
    path: str = "",
    reference_note: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 10,
    response_format: Literal["detailed", "concise"] = "concise",
) -> str:
```

**Docstring** — follow 7-section format from `.agents/reference/adding_tools_guide.md`:
1. One-line summary
2. "Use this when" — one bullet per query_type with specific scenario
3. "Do NOT use this for" — point to obsidian_get_context_tool (read full content) and
   obsidian_vault_manager_tool (modify notes) as future alternatives
4. Args — explain each query_type option, filters structure `{"tags": [...], "date_range": {"days": N},
   "folder": "..."}`, response_format token costs (~30 tokens/result concise, ~150 tokens/result detailed)
5. Returns — JSON-encoded QueryResult structure
6. Performance Notes — execution time estimates per query_type, max limit = 50
7. Examples — one realistic example per query_type (use real-looking vault paths, not "test.md")

**Implementation structure:**
- `effective_limit = min(max(1, limit), 50)` at top
- `vault = VaultManager(ctx.deps.vault_path)` — instantiate fresh each call
- Wrap entire dispatch in `try/except ValueError` → return `QueryResult(..., suggestion=str(exc)).model_dump_json()`
- Dispatch via `_dispatch_query(vault, query_type, ...)` → private `_run_semantic_search`, `_run_list_structure`,
  `_run_find_related`, `_run_search_by_metadata`, `_run_recent_changes` helpers
- concise mode: NoteInfo with only `path`, `title`, `relevance` — all others `None`
- detailed mode: all NoteInfo fields populated
- `suggestion` populated when `results == []` or `truncated == True`
- Return `result.model_dump_json()`
- Log start/complete/failed with timing (`duration_ms`) and result count

**`_run_find_related` specifics**: relevance score = `overlap_count / 10.0` (capped at 1.0). Check
`ref_path.exists()` before calling VaultManager — return QueryResult with suggestion if not found.

**`_run_search_by_metadata` filter handling**:
```python
required_tags: list[str] = filters.get("tags", [])
folder: str = filters.get("folder", "")
days: int | None = filters.get("date_range", {}).get("days")
cutoff_mtime = time.time() - (days * 86400) if days is not None else None
```
Filter passes if: mtime >= cutoff AND all required_tags present in note's frontmatter tags.

**Required imports** for tools file: `from __future__ import annotations`, `import time`,
`from typing import Any, Literal`, `from pydantic_ai import RunContext`,
`from app.core.agent.agent import vault_agent`,
`from app.core.agent.dependencies import AgentDependencies`,
`from app.core.logging import get_logger`,
`from app.features.obsidian_query_vault.obsidian_query_vault_models import NoteInfo, QueryResult`,
`from app.shared.vault.vault_manager import VaultManager`

- **GOTCHA**: `# noqa: SLF001` on any line using `vault._root` or `vault._to_relative()`
- **GOTCHA**: `ctx: RunContext[AgentDependencies]` MUST be the first parameter — Pydantic AI requirement
- **VALIDATE**: `uv run python -c "from app.features.obsidian_query_vault.obsidian_query_vault_tools import obsidian_query_vault_tool; print('tool registered')"`

---

### TASK 9 — CREATE `app/core/agent/tool_registry.py`

```python
"""Central tool registration hub. Import once in main.py.
Each import below triggers @vault_agent.tool as a side effect.
To add a tool: create the feature tools.py, then add its import here.
"""
import app.features.obsidian_query_vault.obsidian_query_vault_tools  # noqa: F401
# import app.features.obsidian_get_context.obsidian_get_context_tools  # noqa: F401
# import app.features.obsidian_vault_manager.obsidian_vault_manager_tools  # noqa: F401
```

- **VALIDATE**: `uv run python -c "import app.core.agent.tool_registry; print('ok')"`

---

### TASK 10 — UPDATE `app/main.py`

- **ADD** after `from app.features.chat import routes as chat_routes`:
  ```python
  import app.core.agent.tool_registry  # noqa: F401  # registers all vault_agent tools
  ```
- **VALIDATE**: `uv run python -c "import app.main; print('ok')"`

---

### TASK 11 — UPDATE `app/core/agent/agent.py`

- **REPLACE** the existing `instructions=` string with text that:
  - Names `obsidian_query_vault_tool` explicitly as the ONLY currently available tool
  - Describes what it does (search, list, find related, filter, recent changes)
  - Instructs Paddy to always use it for vault questions — never guess vault contents
- **VALIDATE**: `uv run python -c "from app.core.agent.agent import vault_agent; print('ok')"`

---

### TASK 12 — UPDATE `app/features/chat/routes.py`

- **FIND**: `deps = AgentDependencies(request_id=get_request_id())`
- **REPLACE** with:
  ```python
  deps = AgentDependencies(
      request_id=get_request_id(),
      vault_path=get_settings().vault_path,
  )
  ```
- `get_settings` is already imported — no new import needed
- **GOTCHA**: Two call sites exist in routes.py — streaming path and non-streaming path. Update both.
- **VALIDATE**: `uv run ruff check app/features/chat/routes.py`

---

### TASK 13 — CREATE test `__init__.py` files

- **CREATE** empty `tests/features/obsidian_query_vault/__init__.py`
- **CREATE** empty `tests/shared/vault/__init__.py`
- **NOTE**: `testpaths = ["app", "tests"]` in pyproject.toml — both directories are already discovered
- **VALIDATE**: `uv run python -c "import tests.shared.vault; import tests.features.obsidian_query_vault"`

---

### TASK 14 — CREATE `tests/shared/vault/test_vault_manager.py`

**Fixture structure** — create in `conftest.py` or inline as `@pytest.fixture`:
```
tmp_path/
  Projects/Alpha.md    — frontmatter: tags: [project, active], body: "Machine learning experiment"
  Projects/Beta.md     — frontmatter: tags: [project, archived], body: "Old Python work"
  Daily/2025-01-15.md  — frontmatter: tags: [daily], body: "Reviewed ML papers"
  README.md            — no frontmatter, body: "# My Vault\nWelcome."
```

Use `tmp_path` fixture (creates a fake vault with at least 3 `.md` files across 2 folders, with frontmatter).
All tests `@pytest.mark.unit`. No `@pytest.mark.asyncio`.

Required test cases (one assertion each — keep tests focused):
- `test_init_valid` — initializes without error
- `test_init_invalid_path` — raises ValueError matching "does not exist"
- `test_list_markdown_files_recursive` — returns files from subdirs
- `test_list_markdown_files_nonrecursive` — only immediate children of folder
- `test_list_markdown_files_missing_folder` — raises ValueError matching "Folder not found"
- `test_search_content_finds_match` — query keyword found in expected file
- `test_search_content_case_insensitive` — UPPERCASE query matches lowercase content
- `test_search_content_no_match` — returns empty list
- `test_get_recent_files` — returns list sorted newest-first
- `test_parse_frontmatter_with_tags` — tags list parsed correctly
- `test_parse_frontmatter_no_frontmatter` — returns `{}`
- `test_get_title_from_h1` — extracts `# Heading` text
- `test_get_title_fallback_stem` — returns filename stem when no heading
- `test_find_related_by_tags` — note sharing tags appears in results
- `test_get_modified_iso_format` — output matches `YYYY-MM-DDTHH:MM:SSZ` pattern

- **VALIDATE**: `uv run pytest tests/shared/vault/ -v -m unit`

---

### TASK 15 — CREATE `tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py`

Use `FakeContext` — a plain Python class, not a mock, not a real RunContext:
```python
class FakeContext:
    def __init__(self, vault_path: str) -> None:
        self.deps = AgentDependencies(vault_path=vault_path, request_id="test-req-id")
```
Call `obsidian_query_vault_tool(ctx, ...)` directly — no agent, no LLM.
Parse all responses with `QueryResult.model_validate_json(raw)`. All `async def`, `@pytest.mark.unit`.
Re-use the same vault fixture structure from `test_vault_manager.py` (same `tmp_path` layout).

Required test cases:
- `test_semantic_search_finds_results` — result list contains expected file path
- `test_semantic_search_missing_query_returns_suggestion` — query=None → suggestion not None, total_found=0
- `test_list_structure_root` — returns files at vault root level
- `test_list_structure_subfolder` — returns only files in named folder
- `test_recent_changes_returns_notes` — result list non-empty
- `test_find_related_missing_reference_returns_suggestion` — reference_note=None → suggestion, no raise
- `test_search_by_metadata_missing_filters_returns_suggestion` — filters=None → suggestion, no raise
- `test_detailed_format_populates_excerpt_and_modified` — excerpt not None, modified not None
- `test_concise_format_excerpt_tags_modified_all_none` — all three fields None
- `test_invalid_vault_path_returns_suggestion_not_exception` — bad vault_path → result with suggestion
- `test_limit_clamped_to_50` — limit=999 completes, result is valid QueryResult

- **VALIDATE**: `uv run pytest tests/features/obsidian_query_vault/ -v -m unit`

---

## VALIDATION COMMANDS

Run in this exact order after all tasks complete:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy .
uv run pyright .
uv run pytest -v -m unit
uv run pytest -v
```

---

## SUGGESTION MESSAGE TEMPLATES

Populate `QueryResult.suggestion` in these scenarios (make messages actionable for the agent):

| Scenario | suggestion value |
|---|---|
| semantic_search, no results | `"No notes found matching '{query}'. Try broader terms or check spelling."` |
| any query_type, truncated | `"Showing {limit} of {total}+ results. Narrow with filters or increase limit."` |
| find_related, no tags on ref | `"No related notes found. The note may have no tags, or no other notes share its tags."` |
| list_structure, empty folder | `"No markdown files found in '{path}'."` |
| search_by_metadata, no matches | `"No notes matched the filters. Try relaxing tags or extending the date range."` |
| any error (ValueError from VaultManager) | Pass `str(exc)` directly — VaultManager errors are already actionable |

---

## EDGE CASES TO HANDLE

- Vault path does not exist → `ValueError` caught at tool level, `QueryResult` with suggestion returned
- Note file with no frontmatter → `parse_frontmatter` returns `{}`, no crash
- Note file with encoding error → `search_content` skips file silently (try/except OSError)
- `query=None` for semantic_search → `ValueError` → QueryResult with suggestion
- `reference_note=None` for find_related → `ValueError` → QueryResult with suggestion
- `filters=None` for search_by_metadata → `ValueError` → QueryResult with suggestion
- Note with no H1 heading → `get_title` falls back to `path.stem`
- `limit > 50` → silently clamped to 50 before dispatch
- Empty vault (no `.md` files) → empty results list with suggestion message

---

## ACCEPTANCE CRITERIA

- [ ] `obsidian_query_vault_tool` appears in vault_agent startup logs as registered tool
- [ ] All 5 query_type operations execute without exception against a tmp vault
- [ ] concise mode: only `path`/`title`/`relevance` populated; detailed: all NoteInfo fields
- [ ] All error paths return `QueryResult` with `suggestion` — never propagate exception to caller
- [ ] `tool_registry.py` is the sole registration point (no tool imports in `main.py` directly)
- [ ] Agent system prompt names `obsidian_query_vault_tool` as the only current tool
- [ ] `vault_path` flows correctly: Settings → AgentDependencies → tool → VaultManager
- [ ] 26 unit tests pass across both test files
- [ ] `ruff check`, `mypy`, `pyright` all report zero errors

---

## NOTES

**Why `str` return type**: Pydantic AI flattens a single `BaseModel` param into the tool schema, merging
its fields with the tool's own parameters. `model_dump_json()` avoids schema pollution entirely.

**Why stdlib frontmatter parser**: PyYAML is not in `pyproject.toml`. Manual parser handles Obsidian's
common patterns (scalars, inline `[a, b]` lists, block `- item` lists) without adding a dependency.

**Why VaultManager is per-request**: `vault_path` comes from request-scoped `AgentDependencies`. VaultManager
is stateless — per-request instantiation is correct and avoids any state leakage between requests.

**`from __future__ import annotations`**: Add to `vault_manager.py` and `obsidian_query_vault_tools.py`.
Required for forward references in type annotations under Python 3.12 strict mode (mypy will flag missing
it on complex generics).

**Confidence: 8/10** — All patterns are established in this plan. Primary risk: strict mypy/pyright
catching `Any` in dispatch helper signatures. Resolve with proper typing before reaching for
`# type: ignore`. Second risk: forgetting `# noqa: SLF001` on `vault._root` accesses inside the tools
file — ruff will fail the build.
