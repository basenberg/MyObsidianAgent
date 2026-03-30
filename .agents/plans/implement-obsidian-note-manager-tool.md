# Feature: obsidian_note_manager_tool

The following plan should be complete, but its important that you validate documentation and
codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Add `obsidian_note_manager_tool` — a Pydantic AI agent tool that gives the vault agent full
write access to the Obsidian vault. The tool consolidates all modification operations (note
CRUD, folder management, bulk tagging, bulk moves, frontmatter updates) into a single
parameter-driven interface following the Anthropic "fewer, smarter tools" principle.

When combined with the existing `obsidian_query_vault_tool`, the agent gains a complete
discover → read → modify loop, enabling workflows like "find all notes tagged urgent from
last week and mark them reviewed" in a minimal number of tool calls.

## User Story

As an Obsidian vault user talking to Paddy
I want the agent to create, update, move, delete, and reorganize my notes
So that I can manage my knowledge base through natural language without opening Obsidian

## Problem Statement

`vault_agent` currently has only `obsidian_query_vault_tool` (read-only). The agent can
find and report on notes but cannot make any changes. Users who ask "create a project note
for X" or "tag all my meeting notes as reviewed" receive no-op responses. Write capability
is the single largest missing feature in the MVP.

## Solution Statement

Implement a new vertical slice `app/features/obsidian_note_manager/` containing models,
a service layer, and the tool. The service layer isolates business logic (validation, safety
guards, bulk coordination) from both the tool function and VaultManager. Extend
`VaultManager` with write methods. Register the tool via `tool_registry.py` and update the
agent's system prompt so it knows the tool exists.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/features/obsidian_note_manager/`, `app/shared/vault/vault_manager.py`, `app/core/agent/agent.py`, `app/core/agent/tool_registry.py`
**Dependencies**: No new external libraries — stdlib `pathlib`, `shutil` only

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `app/features/obsidian_query_vault/obsidian_query_vault_tools.py` — **Primary pattern to mirror**: `@vault_agent.tool` decorator, `RunContext[AgentDependencies]`, `VaultManager(ctx.deps.vault_path)`, dispatch function, `model_dump_json()` return, logger event naming
- `app/features/obsidian_query_vault/obsidian_query_vault_models.py` — Pydantic `BaseModel` response pattern; all response models serialised via `model_dump_json()`
- `app/core/agent/agent.py` (lines 35–50) — `vault_agent` singleton definition and `instructions=` string that must be updated
- `app/core/agent/tool_registry.py` — Side-effect import hub; add one import line here
- `app/core/agent/dependencies.py` — `AgentDependencies` dataclass: `vault_path: str`, `request_id: str`
- `app/shared/vault/vault_manager.py` — Existing read methods pattern; new write methods go here following identical style (docstrings, `ValueError` for actionable errors, `pathlib` only)
- `app/shared/vault/vault_models.py` — `VaultNote`, `VaultFolder` shared domain models
- `tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py` — `FakeContext` pattern, `vault_root` fixture using `tmp_path`, `@pytest.mark.unit`, async test functions
- `tests/conftest.py` — Root `app_client` fixture pattern
- `pyproject.toml` (lines 99–105) — `asyncio_mode = "auto"`, test markers `unit` / `integration`

### New Files to Create

- `app/features/obsidian_note_manager/__init__.py` — Empty package init
- `app/features/obsidian_note_manager/obsidian_note_manager_models.py` — `NoteManagerOperation`, `NoteManagerResult`, `BulkOperationFailure` Pydantic models
- `app/features/obsidian_note_manager/obsidian_note_manager_service.py` — `NoteManagerService`: business logic, validation, safety guards, bulk coordination
- `app/features/obsidian_note_manager/obsidian_note_manager_tool.py` — `@vault_agent.tool` function `obsidian_note_manager_tool`; thin orchestrator delegating to service
- `tests/features/obsidian_note_manager/__init__.py` — Empty
- `tests/features/obsidian_note_manager/test_obsidian_note_manager_models.py` — Model validation unit tests
- `tests/features/obsidian_note_manager/test_obsidian_note_manager_service.py` — Service unit tests with `tmp_path` vault fixture
- `tests/features/obsidian_note_manager/test_obsidian_note_manager_tool.py` — Tool integration unit tests using `FakeContext`

### Files to Update

- `app/shared/vault/vault_manager.py` — Add write methods: `write_note`, `delete_note`, `move_path`, `create_folder`, `delete_folder`, `update_frontmatter`
- `app/core/agent/tool_registry.py` — Uncomment/add import line for new tool module
- `app/core/agent/agent.py` — Update `instructions=` to list the new tool with its purpose
- `tests/shared/vault/test_vault_manager.py` — Add tests for each new write method

### Relevant Documentation — READ BEFORE IMPLEMENTING

- [Pydantic AI Tools](https://ai.pydantic.dev/tools/) — `@agent.tool` decorator registration, `RunContext[DepsType]` injection pattern, JSON-serialisable parameter requirement
- [Anthropic Tool Design](https://www.anthropic.com/engineering/writing-tools-for-agents) — Fewer smarter tools, `confirm_destructive` safety pattern, actionable error messages

### Patterns to Follow

**Naming Conventions:**
```
Feature slice dir:  app/features/obsidian_note_manager/
Models file:        obsidian_note_manager_models.py
Service file:       obsidian_note_manager_service.py
Tool file:          obsidian_note_manager_tool.py
Tool function name: obsidian_note_manager_tool          # registered name on agent
Test files:         test_obsidian_note_manager_*.py
```

**Tool Return Pattern** (mirror query tool):
```python
return result.model_dump_json()   # always return JSON string, never raise
```

**Error Handling in Tools** — return structured error, never raise:
```python
except ValueError as exc:
    logger.exception("vault.note_manager.tool_failed", operation=operation, ...)
    return NoteManagerResult(success=False, message=str(exc), ...).model_dump_json()
```

**Logging Pattern:**
```python
logger.info("vault.note_manager.tool_started", operation=operation, request_id=ctx.deps.request_id)
logger.info("vault.note_manager.tool_completed", operation=operation, affected_count=n, duration_ms=ms)
logger.exception("vault.note_manager.tool_failed", operation=operation, fix_suggestion="...")
```

**VaultManager write method style** — `pathlib` only, `ValueError` with actionable messages:
```python
def write_note(self, relative_path: str, content: str, overwrite: bool = False) -> Path:
    target = self._root / relative_path
    if target.exists() and not overwrite:
        raise ValueError(f"Note already exists at '{relative_path}'. Set overwrite=True to replace.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
```

**Safety guard pattern** — delete requires confirmation:
```python
if not confirm_destructive:
    raise ValueError(
        f"delete_note requires confirm_destructive=True to prevent accidental loss. "
        f"Set confirm_destructive=True to proceed with deleting '{target}'."
    )
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — VaultManager Write Methods

Extend the existing `VaultManager` with write operations before writing any feature code.
All new methods follow the existing pattern: `pathlib` only, actionable `ValueError` messages,
full Google-style docstrings.

**Tasks:**
- Add `write_note(relative_path, content, overwrite=False)` — create or replace a `.md` file
- Add `delete_note(relative_path)` — delete a file (caller must pre-validate `confirm_destructive`)
- Add `move_path(source_relative, destination_relative)` — move file or folder via `shutil.move`
- Add `create_folder(relative_path)` — `mkdir(parents=True, exist_ok=True)`
- Add `delete_folder(relative_path, recursive=False)` — `rmdir` or `shutil.rmtree`
- Add `update_frontmatter(relative_path, changes)` — parse, merge, reserialise YAML front matter
- Write unit tests for all six methods in `tests/shared/vault/test_vault_manager.py`

### Phase 2: Feature Slice — Models and Service

Create the new vertical slice with Pydantic models and a service class.

**Tasks:**
- Create `NoteManagerResult` Pydantic model (response returned by tool)
- Create `BulkOperationFailure` Pydantic model (per-item failure details in bulk ops)
- Create `NoteManagerService` class wrapping `VaultManager`; one method per operation
- Implement all 11 operations in the service: `create_note`, `update_note`, `append_note`,
  `delete_note`, `move_note`, `create_folder`, `delete_folder`, `move_folder`,
  `bulk_tag`, `bulk_move`, `bulk_update_metadata`
- All destructive operations (`delete_note`, `delete_folder`) validate `confirm_destructive`
- Bulk operations collect per-item failures into `BulkOperationFailure` list and report partial success
- Write comprehensive unit tests for service methods

### Phase 3: Tool Registration and Agent Update

Wire the tool into the agent and ensure it appears in the system prompt.

**Tasks:**
- Create the tool module with `@vault_agent.tool` decorator and full agent-optimised docstring
- Register in `tool_registry.py` (one import line)
- Update `agent.py` system prompt `instructions=` to list `obsidian_note_manager_tool`
- Write tool-level unit tests using `FakeContext`

### Phase 4: Testing and Validation

Verify type safety, linting, and test coverage.

**Tasks:**
- Run `uv run mypy .` and `uv run pyright .` — zero errors
- Run `uv run ruff check .` and `uv run ruff format .` — zero violations
- Run full test suite — all green
- Manual smoke test: start server, send a chat message that triggers note creation

---

## STEP-BY-STEP TASKS

### TASK 1 — UPDATE `app/shared/vault/vault_manager.py`

Add write methods as a new section after the existing `# Private helpers` block.

- **ADD** `import shutil` to existing stdlib imports (after `import time`)
- **IMPLEMENT** `write_note(self, relative_path: str, content: str, overwrite: bool = False) -> Path` — resolve path, check existence vs `overwrite`, `mkdir(parents=True, exist_ok=True)`, `write_text`
- **IMPLEMENT** `delete_note(self, relative_path: str) -> Path` — resolve, check exists, `unlink()`; raises `ValueError` if not found (caller checks `confirm_destructive`)
- **IMPLEMENT** `move_path(self, source: str, destination: str) -> Path` — resolve both, validate source exists, `destination.parent.mkdir(parents=True, exist_ok=True)`, `shutil.move(str(src), str(dst))`
- **IMPLEMENT** `create_folder(self, relative_path: str) -> Path` — `mkdir(parents=True, exist_ok=True)`; return resolved path
- **IMPLEMENT** `delete_folder(self, relative_path: str, recursive: bool = False) -> Path` — validate exists and is dir; if not recursive and has contents raise `ValueError`; `rmdir()` or `shutil.rmtree()`
- **IMPLEMENT** `update_frontmatter(self, relative_path: str, changes: dict[str, object]) -> Path` — read file, parse existing frontmatter via `parse_frontmatter()`, merge `changes`, reserialise as YAML block, write back (preserves body content after frontmatter)
- **PATTERN**: mirror `read_file` error style — `ValueError` with actionable message referencing the correct tool to use next
- **GOTCHA**: `shutil.move` returns `str` on some Python versions — cast to `Path`
- **GOTCHA**: `update_frontmatter` must preserve body content (text after the closing `---`)
- **VALIDATE**: `uv run pytest tests/shared/vault/test_vault_manager.py -v -m unit`

### TASK 2 — UPDATE `tests/shared/vault/test_vault_manager.py`

- **ADD** tests for all six new write methods following existing test style
- **IMPLEMENT** `test_write_note_creates_file`, `test_write_note_overwrite_true`, `test_write_note_overwrite_false_raises`
- **IMPLEMENT** `test_delete_note_removes_file`, `test_delete_note_missing_raises`
- **IMPLEMENT** `test_move_path_moves_file`, `test_move_path_creates_parent_dirs`
- **IMPLEMENT** `test_create_folder_creates_nested`, `test_create_folder_idempotent`
- **IMPLEMENT** `test_delete_folder_non_recursive_nonempty_raises`, `test_delete_folder_recursive`
- **IMPLEMENT** `test_update_frontmatter_merges_keys`, `test_update_frontmatter_preserves_body`
- **PATTERN**: `tmp_path` pytest fixture, `@pytest.mark.unit`, no mocking
- **VALIDATE**: `uv run pytest tests/shared/vault/test_vault_manager.py -v -m unit`

### TASK 3 — CREATE `app/features/obsidian_note_manager/__init__.py`

- **CREATE** empty file — package marker only
- **VALIDATE**: `python -c "import app.features.obsidian_note_manager"`

### TASK 4 — CREATE `app/features/obsidian_note_manager/obsidian_note_manager_models.py`

- **CREATE** `BulkOperationFailure(BaseModel)` with fields: `path: str`, `reason: str`
- **CREATE** `NoteManagerResult(BaseModel)` with fields:
  - `success: bool`
  - `operation: str`
  - `affected_count: int`
  - `affected_paths: list[str]`
  - `message: str`
  - `warnings: list[str] | None = None`
  - `partial_success: bool | None = None`
  - `failures: list[BulkOperationFailure] | None = None`
- **IMPORTS**: `from pydantic import BaseModel` only
- **PATTERN**: mirror `obsidian_query_vault_models.py` — Google-style class docstrings, no validators needed
- **VALIDATE**: `uv run mypy app/features/obsidian_note_manager/obsidian_note_manager_models.py`

### TASK 5 — CREATE `app/features/obsidian_note_manager/obsidian_note_manager_service.py`

- **CREATE** class `NoteManagerService` accepting `vault: VaultManager` in `__init__`
- **IMPLEMENT** one public method per operation; each returns `NoteManagerResult`

  Single-note operations:
  - `create_note(target, content, metadata, create_folders) -> NoteManagerResult`
  - `update_note(target, content) -> NoteManagerResult`
  - `append_note(target, content) -> NoteManagerResult`
  - `delete_note(target, confirm_destructive) -> NoteManagerResult`
  - `move_note(target, destination, create_folders) -> NoteManagerResult`

  Folder operations:
  - `create_folder(target, create_folders) -> NoteManagerResult`
  - `delete_folder(target, confirm_destructive) -> NoteManagerResult`
  - `move_folder(target, destination) -> NoteManagerResult`

  Bulk operations:
  - `bulk_tag(targets, metadata) -> NoteManagerResult`
  - `bulk_move(targets, destination) -> NoteManagerResult`
  - `bulk_update_metadata(targets, metadata_changes) -> NoteManagerResult`

- **IMPLEMENT** `_build_content_with_frontmatter(content, metadata) -> str` private helper — serialises `metadata` dict as YAML frontmatter block prepended to `content`
- **IMPLEMENT** `_dispatch(operation, **kwargs) -> NoteManagerResult` — routes `operation` string to method; raises `ValueError` for unknown operations
- **GOTCHA**: `create_note` must call `_build_content_with_frontmatter` only when `metadata` is provided; do not write malformed frontmatter
- **GOTCHA**: bulk operations must catch per-item `ValueError` and continue; collect failures; set `partial_success=True` when `len(failures) < len(targets)`
- **IMPORTS**: `from app.shared.vault.vault_manager import VaultManager`, `from app.features.obsidian_note_manager.obsidian_note_manager_models import NoteManagerResult, BulkOperationFailure`, `from app.core.logging import get_logger`
- **VALIDATE**: `uv run mypy app/features/obsidian_note_manager/obsidian_note_manager_service.py`

### TASK 6 — CREATE `tests/features/obsidian_note_manager/test_obsidian_note_manager_service.py`

- **CREATE** `vault_root` fixture (same pattern as query tool tests — `tmp_path` with pre-populated notes)
- **IMPLEMENT** `test_create_note_creates_file_with_content`
- **IMPLEMENT** `test_create_note_with_metadata_writes_frontmatter`
- **IMPLEMENT** `test_update_note_replaces_content`
- **IMPLEMENT** `test_append_note_adds_to_existing`
- **IMPLEMENT** `test_delete_note_without_confirm_raises_in_result`
- **IMPLEMENT** `test_delete_note_with_confirm_removes_file`
- **IMPLEMENT** `test_move_note_moves_to_destination`
- **IMPLEMENT** `test_create_folder_creates_directory`
- **IMPLEMENT** `test_bulk_tag_updates_all_notes`
- **IMPLEMENT** `test_bulk_tag_partial_failure_reports_failures`
- **IMPLEMENT** `test_bulk_move_moves_all_targets`
- **IMPLEMENT** `test_dispatch_unknown_operation_returns_failure`
- **PATTERN**: `@pytest.mark.unit`, all sync (service methods are sync), assert `result.success`, `result.affected_paths`, `result.message`
- **VALIDATE**: `uv run pytest tests/features/obsidian_note_manager/test_obsidian_note_manager_service.py -v -m unit`

### TASK 7 — CREATE `app/features/obsidian_note_manager/obsidian_note_manager_tool.py`

- **CREATE** module docstring explaining side-effect import registration pattern
- **IMPLEMENT** `@vault_agent.tool` async function `obsidian_note_manager_tool` with signature:
  ```python
  async def obsidian_note_manager_tool(
      ctx: RunContext[AgentDependencies],
      operation: Literal[
          "create_note", "update_note", "append_note", "delete_note", "move_note",
          "create_folder", "delete_folder", "move_folder",
          "bulk_tag", "bulk_move", "bulk_update_metadata",
      ],
      target: str | None = None,
      targets: list[str] | None = None,
      content: str | None = None,
      destination: str | None = None,
      metadata: dict[str, object] | None = None,
      metadata_changes: dict[str, object] | None = None,
      confirm_destructive: bool = False,
      create_folders: bool = True,
  ) -> str:
  ```
- **IMPLEMENT** full agent-optimised docstring (7 required sections: one-liner, Use this when, Do NOT use, Args, Returns, Performance Notes, Examples)
  - "Use this when" must cover: creating new notes, updating/appending existing notes, deleting notes, moving notes, folder management, bulk tagging, bulk metadata updates
  - "Do NOT use" must reference `obsidian_query_vault_tool` for finding notes and reading content
  - Args section: explain `confirm_destructive=True` requirement for delete operations; explain `targets` vs `target` distinction; token cost guidance on response
  - Performance Notes: single ops ~5-50ms; bulk ops scale linearly with target count
  - Examples: 4+ realistic examples with actual vault paths
- **IMPLEMENT** function body:
  1. `start = time.time()`
  2. `logger.info("vault.note_manager.tool_started", ...)`
  3. `vault = VaultManager(ctx.deps.vault_path)`
  4. `service = NoteManagerService(vault)`
  5. Call `service._dispatch(operation, target=target, targets=targets, ...)` in try/except
  6. On `ValueError`: log exception, return failure `NoteManagerResult`
  7. `duration_ms = ...`; log completed; `return result.model_dump_json()`
- **IMPORTS**: `from app.core.agent.agent import vault_agent`, `from app.core.agent.dependencies import AgentDependencies`, `from app.features.obsidian_note_manager.obsidian_note_manager_models import NoteManagerResult`, `from app.features.obsidian_note_manager.obsidian_note_manager_service import NoteManagerService`, `from app.shared.vault.vault_manager import VaultManager`, `from app.core.logging import get_logger`
- **GOTCHA**: `from __future__ import annotations` at top (matches query tool)
- **GOTCHA**: `dict[str, object]` not `dict[str, Any]` — avoids `Any` in strict mode; if `Any` needed add `# type: ignore` with inline comment
- **VALIDATE**: `uv run mypy app/features/obsidian_note_manager/obsidian_note_manager_tool.py`

### TASK 8 — CREATE `tests/features/obsidian_note_manager/test_obsidian_note_manager_tool.py`

- **MIRROR** `tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py` exactly for `FakeContext` pattern
- **IMPLEMENT** `FakeContext` class with `deps = AgentDependencies(vault_path=..., request_id="test-tool-req")`
- **IMPLEMENT** `vault_root` fixture
- **IMPLEMENT** `test_create_note_tool_returns_success_json`
- **IMPLEMENT** `test_delete_note_tool_without_confirm_returns_failure`
- **IMPLEMENT** `test_delete_note_tool_with_confirm_returns_success`
- **IMPLEMENT** `test_update_note_tool_replaces_content`
- **IMPLEMENT** `test_bulk_tag_tool_tags_all_targets`
- **IMPLEMENT** `test_tool_invalid_vault_returns_failure_json` — pass nonexistent vault path, assert `success == False`
- **PATTERN**: `result = NoteManagerResult.model_validate_json(raw)`, assert on `result.success`, `result.operation`, `result.affected_paths`
- **VALIDATE**: `uv run pytest tests/features/obsidian_note_manager/test_obsidian_note_manager_tool.py -v -m unit`

### TASK 9 — UPDATE `app/core/agent/tool_registry.py`

- **ADD** import line after existing query vault import:
  ```python
  import app.features.obsidian_note_manager.obsidian_note_manager_tool  # noqa: F401  # pyright: ignore[reportUnusedImport]
  ```
- **UPDATE** module docstring to reflect two registered tools
- **VALIDATE**: `python -c "import app.core.agent.tool_registry"` — no import errors

### TASK 10 — UPDATE `app/core/agent/agent.py`

- **UPDATE** `instructions=` string to add `obsidian_note_manager_tool` alongside existing tool listing
- Replace the current instructions block:
  ```python
  instructions=(
      "You are Paddy, an AI assistant for an Obsidian knowledge vault. "
      "Be concise and precise.\n\n"
      "Available tools:\n"
      "- obsidian_query_vault_tool: Search and discover vault notes. ...\n"
      "- obsidian_note_manager_tool: Create, update, append, delete, and move notes "
      "and folders. Supports bulk tagging and bulk metadata updates. Always use "
      "obsidian_query_vault_tool to find note paths BEFORE passing them to this tool.\n\n"
      "Workflow: discover with obsidian_query_vault_tool → modify with "
      "obsidian_note_manager_tool. Never guess vault paths — search first."
  ),
  ```
- **GOTCHA**: Remove the stale comment "This is your ONLY tool right now." from the instructions
- **VALIDATE**: `uv run mypy app/core/agent/agent.py`

### TASK 11 — FINAL VALIDATION RUN

- **VALIDATE**: `uv run ruff check .`
- **VALIDATE**: `uv run ruff format . --check`
- **VALIDATE**: `uv run mypy .`
- **VALIDATE**: `uv run pyright .`
- **VALIDATE**: `uv run pytest -v -m unit` — all unit tests green
- **VALIDATE**: `uv run pytest -v` — full suite green (excluding integration markers)

---

## TESTING STRATEGY

### Unit Tests

All tests are `@pytest.mark.unit`. No external dependencies, no running server, no real vault.

- **VaultManager write tests** (`tests/shared/vault/test_vault_manager.py`): use `tmp_path`, test each method with valid input, invalid input, and edge cases (overwrite, non-empty folder, missing parent)
- **Service tests** (`test_obsidian_note_manager_service.py`): instantiate `NoteManagerService(VaultManager(str(tmp_path)))`, call methods directly, assert on `NoteManagerResult` fields
- **Tool tests** (`test_obsidian_note_manager_tool.py`): use `FakeContext`, call `await obsidian_note_manager_tool(ctx, ...)`, parse JSON result via `NoteManagerResult.model_validate_json(raw)`
- **Model tests** (`test_obsidian_note_manager_models.py`): validate field defaults, serialization roundtrips

### Integration Tests

Not required for this feature. The vault runs on the file system with no network dependencies, so `tmp_path` unit tests provide equivalent coverage. If a `/vault`-mounted integration test is desired later, mark with `@pytest.mark.integration`.

### Edge Cases

- `create_note` when parent folder does not exist and `create_folders=False` → returns failure with actionable message
- `create_note` when file already exists → returns failure (no silent overwrite)
- `delete_note` without `confirm_destructive=True` → returns failure with clear instruction
- `delete_folder` on non-empty folder without `recursive` → returns failure
- `bulk_tag` where some paths don't exist → partial success with `failures` populated
- `bulk_move` where destination doesn't exist → auto-create or fail depending on `create_folders`
- `update_frontmatter` on a note with no existing frontmatter → creates new frontmatter block
- Tool called with `target=None` for single-target operation → returns failure with parameter guidance
- Tool called with `targets=None` for bulk operation → returns failure with parameter guidance
- Invalid `vault_path` (doesn't exist) → `VaultManager.__init__` raises `ValueError` → tool returns failure JSON (never crashes)

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check .
uv run ruff format . --check
```

### Level 2: Type Checking

```bash
uv run mypy .
uv run pyright .
```

### Level 3: Unit Tests

```bash
# New feature tests only (fast feedback)
uv run pytest tests/features/obsidian_note_manager/ -v -m unit

# VaultManager write method tests
uv run pytest tests/shared/vault/test_vault_manager.py -v -m unit

# Full unit suite — no regressions
uv run pytest -v -m unit
```

### Level 4: Full Test Suite

```bash
uv run pytest -v
```

### Level 5: Manual Smoke Test

Start the server and send a chat completion request that exercises the new tool:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal:
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "paddy",
    "messages": [{"role": "user", "content": "Create a test note at Test/smoke-test.md with content Hello World"}]
  }' | jq '.choices[0].message.content'
```

Verify the file was created at `$VAULT_PATH/Test/smoke-test.md`.

---

## ACCEPTANCE CRITERIA

- [ ] `obsidian_note_manager_tool` is registered on `vault_agent` and appears in Pydantic AI tool list
- [ ] All 11 operations (`create_note`, `update_note`, `append_note`, `delete_note`, `move_note`, `create_folder`, `delete_folder`, `move_folder`, `bulk_tag`, `bulk_move`, `bulk_update_metadata`) are implemented and reachable via the `operation` parameter
- [ ] Destructive operations (`delete_note`, `delete_folder`) refuse without `confirm_destructive=True` and return a clear failure result (not an exception)
- [ ] Bulk operations support partial success — individual item failures are collected in `failures` field, successful items are still processed
- [ ] `VaultManager` has 6 new write methods, all type-annotated, all with Google docstrings
- [ ] `uv run mypy .` passes with zero errors
- [ ] `uv run pyright .` passes with zero errors
- [ ] `uv run ruff check .` passes with zero violations
- [ ] `uv run pytest -v -m unit` passes — all unit tests green including new tests
- [ ] Agent system prompt updated — no stale "ONLY tool" comment, new tool listed with purpose
- [ ] Tool docstring contains all 7 required sections (one-liner, Use this when, Do NOT use, Args, Returns, Performance Notes, Examples) with realistic vault path examples

---

## COMPLETION CHECKLIST

- [ ] Task 1: VaultManager write methods added and tested
- [ ] Task 2: VaultManager write method tests pass
- [ ] Task 3: `__init__.py` created
- [ ] Task 4: Models file created — `NoteManagerResult`, `BulkOperationFailure`
- [ ] Task 5: Service file created — all 11 operation methods + `_dispatch`
- [ ] Task 6: Service unit tests pass
- [ ] Task 7: Tool file created with full agent-optimised docstring
- [ ] Task 8: Tool unit tests pass using `FakeContext`
- [ ] Task 9: `tool_registry.py` updated — new import line added
- [ ] Task 10: `agent.py` system prompt updated — two tools listed, stale comment removed
- [ ] Task 11: All validation commands execute successfully
- [ ] Manual smoke test confirms note creation in vault

---

## NOTES

**Why a service layer?** The existing `obsidian_query_vault_tools.py` embeds helper functions (`_dispatch_query`, `_run_semantic_search`, etc.) directly in the tool module. For note management, business logic is heavier (bulk coordination, frontmatter serialisation, safety validation) — a dedicated `NoteManagerService` class makes that logic unit-testable without constructing a `RunContext`. This is an additive pattern, not a change to the query tool.

**`dict[str, object]` vs `dict[str, Any]`** — Pyright strict mode flags `Any` in function signatures as `reportUnknownParameterType`. Use `dict[str, object]` for the `metadata` and `metadata_changes` parameters; inside implementation methods, cast values to concrete types before use (e.g., `tags = [str(t) for t in metadata.get("tags", [])]`). This matches the pattern already used in the query tool's `_run_search_by_metadata`.

**`update_frontmatter` serialisation** — The existing `parse_frontmatter` is a read-only custom parser. For writing, serialise the merged dict as a simple YAML block (key: value lines, list values as `[a, b, c]` inline lists). Do not introduce a PyYAML dependency — a hand-rolled serialiser suffices for the flat frontmatter structures used in Obsidian. Only scalar, list, and string values are needed.

**Pyproject target** — `pyproject.toml` says `requires-python = ">=3.12"` and `pythonPlatform = "Darwin"` in Pyright config. The platform mismatch (running on Windows) may surface minor Pyright path warnings — these are pre-existing, not introduced by this feature.

<!-- EOF -->
