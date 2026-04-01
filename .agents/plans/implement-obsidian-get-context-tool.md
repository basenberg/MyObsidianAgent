# Feature: implement-obsidian-get-context-tool

The following plan should be complete, but validate documentation and codebase patterns before implementing. Pay special attention to naming of existing utils, types, and models — import from the right files.

## Feature Description

Add the third and final consolidated tool, `obsidian_get_context_tool`, which provides workflow-oriented note reading with optional surrounding context. It returns full note content (not excerpts), with optional metadata, related notes, and backlinks compiled for synthesis tasks. This completes the three-tool architecture defined in the PRD.

## User Story

As a vault user  
I want to read note content with surrounding context (metadata, related notes, backlinks)  
So that I can synthesize information and understand note relationships through natural language

## Problem Statement

`obsidian_query_vault_tool` intentionally returns only summaries and excerpts to avoid token waste during discovery. Once the agent knows which note(s) to read, there is no tool to retrieve full content. Without `obsidian_get_context_tool`, the agent cannot read, synthesize, or present note content to the user.

## Solution Statement

Implement `obsidian_get_context_tool` following the exact patterns of the two existing tools. It dispatches to per-`context_type` handlers via a service class, returns `ContextResult.model_dump_json()`, and never raises exceptions. The `read_note`, `read_multiple`, `gather_related`, `daily_note`, and `note_with_backlinks` operations cover all reading workflows.

## Feature Metadata

**Feature Type**: New Capability  
**Estimated Complexity**: Medium  
**Primary Systems Affected**: `features/obsidian_get_context/`, `core/agent/tool_registry.py`, `core/agent/agent.py`  
**Dependencies**: No new packages — uses only existing VaultManager, structlog, pydantic

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `app/features/obsidian_query_vault/obsidian_query_vault_tools.py` (lines 1–22) — Module docstring pattern + import block to mirror exactly
- `app/features/obsidian_query_vault/obsidian_query_vault_tools.py` (lines 25–196) — Full `@vault_agent.tool` function pattern: signature, docstring, logging, error handling, return
- `app/features/obsidian_query_vault/obsidian_query_vault_models.py` — Pydantic model structure to follow
- `app/features/obsidian_note_manager/obsidian_note_manager_service.py` (lines 23–95) — Service `__init__`, per-operation method, and `dispatch()` pattern
- `app/features/obsidian_note_manager/obsidian_note_manager_models.py` — Error-result model pattern
- `app/shared/vault/vault_manager.py` (lines 119–194) — `read_file`, `search_content`, `find_related_by_tags` implementations
- `app/shared/vault/vault_manager.py` (lines 200–292) — `parse_frontmatter`, `get_title`, `get_modified_iso`, `to_relative`
- `app/core/agent/tool_registry.py` — Commented placeholder already exists on line 22; uncomment to register
- `app/core/agent/agent.py` (lines 27–51) — Agent instructions to update with new tool description
- `app/core/agent/dependencies.py` — `AgentDependencies` dataclass (`vault_path`, `request_id`)
- `tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py` — FakeContext + tmp_path + model_validate_json test pattern
- `tests/conftest.py` — Shared fixtures (`test_env_vars`)

### New Files to Create

- `app/features/obsidian_get_context/__init__.py` — Empty init
- `app/features/obsidian_get_context/obsidian_get_context_models.py` — `NoteContent`, `BacklinkInfo`, `ContextResult`
- `app/features/obsidian_get_context/obsidian_get_context_service.py` — Business logic for all 5 context_types
- `app/features/obsidian_get_context/obsidian_get_context_tools.py` — Tool registration (plural, matches query_vault naming)
- `tests/features/obsidian_get_context/__init__.py` — Empty init
- `tests/features/obsidian_get_context/test_obsidian_get_context_models.py` — Model validation tests
- `tests/features/obsidian_get_context/test_obsidian_get_context_service.py` — Service unit tests
- `tests/features/obsidian_get_context/test_obsidian_get_context_tools.py` — Tool integration tests

### Relevant Documentation

- `.agents/reference/mvp-tool-designs.md` (lines 313–423) — Exact spec: parameter names, ContextResult schema, BacklinkInfo schema, design rationale
- `.agents/reference/adding_tools_guide.md` — Full docstring template (7 required sections)

### Patterns to Follow

**Module docstring (tool file):**
```python
"""obsidian_get_context_tools — vault context reading tool for vault_agent.

Importing this module registers obsidian_get_context_tool on vault_agent via the
@vault_agent.tool decorator (side effect). Import through tool_registry.py only.
"""
```

**Import block (mirror query_vault exactly):**
```python
from __future__ import annotations
import time
from typing import Literal
from pydantic_ai import RunContext
from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.logging import get_logger
from app.features.obsidian_get_context.obsidian_get_context_models import ContextResult
from app.features.obsidian_get_context.obsidian_get_context_service import GetContextService
from app.shared.vault.vault_manager import VaultManager
logger = get_logger(__name__)
```

**Logging event names (vault.context.* namespace):**
```
vault.context.tool_started    — at entry, log context_type + request_id
vault.context.tool_completed  — at exit, log duration_ms
vault.context.tool_failed     — in except block via logger.exception()
```

**Error return (never raise in tool function):**
```python
except (ValueError, OSError) as exc:
    logger.exception("vault.context.tool_failed", context_type=context_type,
                     fix_suggestion="Verify note path via obsidian_query_vault_tool first")
    return ContextResult(
        primary_note=NoteContent(path="", title="", content=str(exc), metadata=None, word_count=0),
        token_estimate=0,
        context_type=context_type,
    ).model_dump_json()
```

**Service dispatch pattern (mirror NoteManagerService.dispatch):**
```python
def dispatch(self, context_type: str, **kwargs) -> ContextResult:
    if context_type == "read_note": return self.read_note(...)
    if context_type == "read_multiple": return self.read_multiple(...)
    ...
    raise ValueError(f"Unknown context_type: '{context_type}'. ...")
```

**Backlink discovery (no VaultManager method exists — implement in service):**
Use `vault.search_content(title_or_stem, limit=50)` to find notes containing the target's wiki-link. Filter the excerpt for `[[` context. Map results to `BacklinkInfo`.

**Daily note resolution (no VaultManager method — implement in service):**
Try candidate paths in order: `Daily Notes/{date}.md`, `Journal/{date}.md`, `{date}.md`. If date="today", use `datetime.date.today().isoformat()`.

**Token estimate (in ContextResult):**
```python
# Rough: 1 token ≈ 4 chars
token_estimate = len(result.model_dump_json()) // 4
```

**Concise format (content truncation for read_note / related):**
```python
# concise: first 200 words of content
if concise:
    words = content.split()
    content = " ".join(words[:200]) + ("…" if len(words) > 200 else "")
```

---

## IMPLEMENTATION PLAN

### Phase 1: Models

Define the response schema from `mvp-tool-designs.md` lines 391–410.

**Tasks:**
- Create `NoteContent`, `BacklinkInfo`, `ContextResult` Pydantic models
- Add `context_type: str` and `error: str | None = None` to `ContextResult` for agent steering

### Phase 2: Service

Implement `GetContextService` with one method per `context_type`.

**Tasks:**
- `_build_note_content(path, include_metadata, concise)` → `NoteContent` private helper
- `read_note(target, include_metadata, include_backlinks, concise)` → `ContextResult`
- `read_multiple(targets, include_metadata, concise)` → `ContextResult` (primary_note = first, related_notes = rest)
- `gather_related(target, include_metadata, max_related, concise)` → `ContextResult`
- `daily_note(date, include_metadata, concise)` → `ContextResult`
- `note_with_backlinks(target, include_metadata, max_related, concise)` → `ContextResult`
- `dispatch(context_type, **kwargs)` → `ContextResult`

### Phase 3: Tool + Registration

Wire the tool function and register it.

**Tasks:**
- Create `obsidian_get_context_tools.py` with `@vault_agent.tool` decorated function
- Uncomment the placeholder in `tool_registry.py` line 22
- Update `tool_registry.py` header comment (registered tool count: 2 → 3)
- Update `agent.py` instructions to describe the new tool and the 3-step workflow

### Phase 4: Tests

Mirror test file structure from `obsidian_query_vault` and `obsidian_note_manager` tests.

---

## STEP-BY-STEP TASKS

### CREATE `app/features/obsidian_get_context/__init__.py`
- **IMPLEMENT**: Empty file
- **VALIDATE**: `python -c "import app.features.obsidian_get_context"`

### CREATE `app/features/obsidian_get_context/obsidian_get_context_models.py`
- **IMPLEMENT**: Three Pydantic models:
  ```python
  class NoteContent(BaseModel):
      path: str
      title: str
      content: str
      metadata: dict[str, Any] | None = None
      word_count: int = 0

  class BacklinkInfo(BaseModel):
      note_path: str
      note_title: str
      context: str  # surrounding text where link appears

  class ContextResult(BaseModel):
      primary_note: NoteContent
      related_notes: list[NoteContent] | None = None
      backlinks: list[BacklinkInfo] | None = None
      metadata_summary: dict[str, Any] | None = None
      token_estimate: int = 0
      context_type: str = ""
      error: str | None = None
  ```
- **IMPORTS**: `from __future__ import annotations`, `from typing import Any`, `from pydantic import BaseModel`
- **GOTCHA**: `dict[str, Any]` not `dict` — MyPy requires explicit type params. Import `Any` from `typing`.
- **VALIDATE**: `uv run mypy app/features/obsidian_get_context/obsidian_get_context_models.py`

### CREATE `app/features/obsidian_get_context/obsidian_get_context_service.py`
- **IMPLEMENT**: `GetContextService` class with `__init__(self, vault: VaultManager)`, private helpers, and one public method per context_type plus `dispatch()`
- **PATTERN**: `app/features/obsidian_note_manager/obsidian_note_manager_service.py` (lines 23–95 for `__init__` + method structure, lines 655–716 for `dispatch`)
- **IMPLEMENT** `_build_note_content(path: Path, include_metadata: bool, concise: bool) -> NoteContent`:
  - Call `vault.read_file(path)` for content
  - If concise: truncate to first 200 words + "…" if longer
  - If include_metadata: call `vault.parse_frontmatter(path)` for metadata
  - `word_count = len(content.split())`; `title = vault.get_title(path)`; `path_str = vault.to_relative(path)`
- **IMPLEMENT** `_find_backlinks(target: Path, limit: int) -> list[BacklinkInfo]`:
  - `stem = target.stem` (filename without extension)
  - `title = vault.get_title(target)`
  - Call `vault.search_content(f"[[{stem}]]", limit=limit)` and `vault.search_content(f"[[{title}]]", limit=limit)` then deduplicate by path
  - Map to `BacklinkInfo(note_path=vault.to_relative(p), note_title=vault.get_title(p), context=excerpt)`
  - Exclude target itself from results
- **IMPLEMENT** `_resolve_daily_note(date_str: str) -> Path`:
  - If date_str == "today": `date_str = datetime.date.today().isoformat()`
  - Try candidates: `vault._root / "Daily Notes" / f"{date_str}.md"`, `vault._root / "Journal" / f"{date_str}.md"`, `vault._root / f"{date_str}.md"`
  - Return first that exists; raise `ValueError` with actionable message if none found
- **IMPLEMENT** `read_note(target, include_metadata, include_backlinks, max_related, concise) -> ContextResult`:
  - Validate target not None; resolve absolute path; call `_build_note_content`; optionally call `_find_backlinks`
  - Build `metadata_summary` from frontmatter if include_metadata
- **IMPLEMENT** `read_multiple(targets, include_metadata, concise) -> ContextResult`:
  - First target → `primary_note`; rest → `related_notes` list
  - Skip missing notes with warning in `error` field
- **IMPLEMENT** `gather_related(target, include_metadata, max_related, concise) -> ContextResult`:
  - Use `vault.find_related_by_tags(abs_path, limit=max_related)` for related notes
  - If no tags: return result with `error="No tags found on target note — gather_related requires frontmatter tags."`
- **IMPLEMENT** `daily_note(date_str, include_metadata, concise) -> ContextResult`:
  - Call `_resolve_daily_note(date_str)` then `_build_note_content`
- **IMPLEMENT** `note_with_backlinks(target, include_metadata, max_related, concise) -> ContextResult`:
  - `_build_note_content` + `_find_backlinks(abs_path, limit=max_related)`
- **IMPLEMENT** `dispatch(context_type, **kwargs) -> ContextResult`:
  - Route to the correct method; raise `ValueError` for unknown context_type
- **IMPORTS**: `from __future__ import annotations`, `import datetime`, `from pathlib import Path`, `from app.core.logging import get_logger`, `from app.features.obsidian_get_context.obsidian_get_context_models import BacklinkInfo, ContextResult, NoteContent`, `from app.shared.vault.vault_manager import VaultManager`
- **GOTCHA**: `vault._root` is a private attribute — access it only in `_resolve_daily_note`. Alternatively, accept a `vault_root: Path` in `__init__` separately. Prefer `vault._root` to avoid API surface bloat since it's an internal service.
- **VALIDATE**: `uv run mypy app/features/obsidian_get_context/obsidian_get_context_service.py`

### CREATE `app/features/obsidian_get_context/obsidian_get_context_tools.py`
- **IMPLEMENT**: Module docstring + imports + `@vault_agent.tool` function
- **PATTERN**: `app/features/obsidian_query_vault/obsidian_query_vault_tools.py` (lines 1–22 module docstring, lines 25–196 tool function)
- **IMPLEMENT** tool signature:
  ```python
  @vault_agent.tool
  async def obsidian_get_context_tool(
      ctx: RunContext[AgentDependencies],
      context_type: Literal["read_note", "read_multiple", "gather_related", "daily_note", "note_with_backlinks"],
      target: str | None = None,
      targets: list[str] | None = None,
      date: str | None = None,
      include_metadata: bool = True,
      include_backlinks: bool = False,
      max_related: int = 3,
      response_format: Literal["detailed", "concise"] = "detailed",
  ) -> str:
  ```
- **IMPLEMENT** docstring following the 7-element template from `adding_tools_guide.md`:
  - One-line summary
  - "Use this when" (5 bullets — one per context_type)
  - "Do NOT use this for" (discovery → use query_vault; modifications → use note_manager)
  - Args with guidance for each param
  - Returns: JSON-serialized ContextResult
  - Performance Notes: detailed ~500–5000 tokens, concise ~100–300 tokens
  - Examples: one per context_type with realistic paths
- **IMPLEMENT** body:
  ```python
  start = time.time()
  logger.info("vault.context.tool_started", context_type=context_type, request_id=ctx.deps.request_id)
  try:
      vault = VaultManager(ctx.deps.vault_path)
      service = GetContextService(vault)
      result = service.dispatch(
          context_type, target=target, targets=targets, date=date,
          include_metadata=include_metadata, include_backlinks=include_backlinks,
          max_related=max_related, concise=response_format == "concise",
      )
  except (ValueError, OSError) as exc:
      logger.exception("vault.context.tool_failed", context_type=context_type,
                       fix_suggestion="Verify note path with obsidian_query_vault_tool first")
      result = ContextResult(
          primary_note=NoteContent(path="", title="error", content=str(exc), word_count=0),
          context_type=context_type, error=str(exc),
      )
  duration_ms = round((time.time() - start) * 1000, 2)
  logger.info("vault.context.tool_completed", context_type=context_type, duration_ms=duration_ms)
  return result.model_dump_json()
  ```
- **VALIDATE**: `uv run python -c "import app.features.obsidian_get_context.obsidian_get_context_tools"`

### UPDATE `app/core/agent/tool_registry.py`
- **IMPLEMENT**: Uncomment line 22: `import app.features.obsidian_get_context.obsidian_get_context_tools  # noqa: F401  # pyright: ignore[reportUnusedImport]`
- **UPDATE** module docstring: "Registered tools (3):" and add bullet for `obsidian_get_context_tool`
- **VALIDATE**: `uv run python -c "from app.core.agent import tool_registry"`

### UPDATE `app/core/agent/agent.py` — agent instructions
- **ADD** to the instructions string: describe `obsidian_get_context_tool` (reads full content; use after query_vault discovers paths)
- **UPDATE** workflow line: "discover → read → modify" (was "discover → modify")
- **VALIDATE**: `uv run python -c "from app.core.agent.agent import vault_agent; print(vault_agent)"`

### CREATE `tests/features/obsidian_get_context/__init__.py`
- **IMPLEMENT**: Empty file

### CREATE `tests/features/obsidian_get_context/test_obsidian_get_context_models.py`
- **IMPLEMENT**: Validate model defaults and round-trip JSON serialization
- **PATTERN**: `tests/features/obsidian_note_manager/test_obsidian_note_manager_models.py`
- **VALIDATE**: `uv run pytest tests/features/obsidian_get_context/test_obsidian_get_context_models.py -v`

### CREATE `tests/features/obsidian_get_context/test_obsidian_get_context_service.py`
- **IMPLEMENT**: Unit tests for each service method using `tmp_path` vault fixture
- **PATTERN**: `tests/features/obsidian_note_manager/test_obsidian_note_manager_service.py`
- **Test cases**:
  - `test_read_note_returns_full_content` — content matches written file
  - `test_read_note_concise_truncates_content` — content ≤ 200 words + "…"
  - `test_read_note_includes_metadata` — metadata dict populated from frontmatter
  - `test_read_note_missing_raises_error` — ValueError message contains path
  - `test_read_multiple_first_is_primary` — primary_note = first target
  - `test_gather_related_uses_tags` — related_notes populated when tags overlap
  - `test_gather_related_no_tags_returns_error` — error field set when no tags
  - `test_daily_note_today` — resolves today's date, finds note in Daily Notes/
  - `test_daily_note_not_found` — ContextResult with error message
  - `test_note_with_backlinks_finds_links` — backlinks list populated
- **VALIDATE**: `uv run pytest tests/features/obsidian_get_context/test_obsidian_get_context_service.py -v -m unit`

### CREATE `tests/features/obsidian_get_context/test_obsidian_get_context_tools.py`
- **IMPLEMENT**: Full tool tests via `FakeContext` + `model_validate_json`
- **PATTERN**: `tests/features/obsidian_query_vault/test_obsidian_query_vault_tools.py` (FakeContext class, vault_root fixture, async test functions)
- **Test cases**:
  - `test_read_note_tool_returns_json` — JSON parses to ContextResult, primary_note populated
  - `test_read_note_tool_concise_format` — content shorter than detailed
  - `test_read_multiple_tool_returns_related_notes` — related_notes list has n-1 items
  - `test_gather_related_tool` — related_notes populated for tagged note
  - `test_daily_note_tool_today` — finds daily note fixture
  - `test_note_with_backlinks_tool` — backlinks populated when other notes reference target
  - `test_tool_handles_missing_note_gracefully` — returns JSON, not exception; error field set
- **VALIDATE**: `uv run pytest tests/features/obsidian_get_context/test_obsidian_get_context_tools.py -v -m unit`

---

## TESTING STRATEGY

### Unit Tests

Each service method tested in isolation with `tmp_path` vault. No mocking — VaultManager wraps real files. Mark all `@pytest.mark.unit`. Vault fixture should include:
- A tagged note with frontmatter: `tags: [project, ml]`
- A note without frontmatter (for error-path tests)
- A "Daily Notes/{today}.md" for daily_note tests
- A note that links to the primary note: `[[Primary Note]]` in body

### Integration Tests

Not required at this stage — unit tests with real files via tmp_path are sufficient for a file-system-only tool.

### Edge Cases

- `target=None` for operations that require it → actionable error message
- `targets=[]` for read_multiple → error result (not crash)
- Note with no frontmatter + `include_metadata=True` → `metadata=None`, no crash
- `max_related=0` for gather_related → `related_notes=[]`
- `date="today"` resolves to current date
- Backlink search when no other notes reference target → `backlinks=[]`
- Very long note in concise mode → truncated at word boundary

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
uv run ruff check app/features/obsidian_get_context/ tests/features/obsidian_get_context/
uv run ruff format --check app/features/obsidian_get_context/ tests/features/obsidian_get_context/
```

### Level 2: Type Checking
```bash
uv run mypy app/features/obsidian_get_context/
uv run pyright app/features/obsidian_get_context/
```

### Level 3: Unit Tests
```bash
uv run pytest tests/features/obsidian_get_context/ -v -m unit
```

### Level 4: Full Suite (Regression)
```bash
uv run pytest tests/ -v -m unit
```

### Level 5: Manual Smoke Test
```bash
# Start server and send test request via curl
docker compose up --build -d
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"paddy","messages":[{"role":"user","content":"Read my most recent daily note"}],"stream":false}' | jq .
```

---

## ACCEPTANCE CRITERIA

- [ ] All 5 context_types return valid `ContextResult` JSON
- [ ] `response_format="concise"` truncates content to ≤ 200 words
- [ ] Missing note returns JSON with `error` field — does not raise to caller
- [ ] Backlinks found via `[[wiki-link]]` search using note title/stem
- [ ] Daily note resolves "today" to current date and finds file in `Daily Notes/` or `Journal/`
- [ ] `obsidian_get_context_tool` registered in `vault_agent` (tool_registry uncommented)
- [ ] Agent instructions updated to include tool description and 3-step workflow
- [ ] All validation commands pass with zero errors
- [ ] No `# type: ignore` or `# pyright: ignore` added
- [ ] No regressions — full unit suite passes

---

## COMPLETION CHECKLIST

- [ ] All tasks completed top-to-bottom
- [ ] Each task's VALIDATE command passed immediately after
- [ ] `uv run ruff check .` clean
- [ ] `uv run mypy .` clean
- [ ] `uv run pyright .` clean
- [ ] `uv run pytest tests/ -v -m unit` — all green
- [ ] Manual smoke test confirms agent uses the tool

---

## NOTES

**File naming**: Use `obsidian_get_context_tools.py` (plural) matching `obsidian_query_vault_tools.py`. The `tool_registry.py` placeholder already uses this name.

**No new VaultManager methods**: Backlink discovery and daily-note resolution are implemented entirely in the service layer using existing `search_content` and path construction. This keeps VaultManager focused on primitives.

**`read_multiple` primary_note design**: The PRD spec's `ContextResult` has a single `primary_note`. For `read_multiple`, use the first target as `primary_note` and the rest as `related_notes`. Document this in the docstring.

**`token_estimate` calculation**: Use `len(result.model_dump_json()) // 4` after building the full result. This is a rough but consistent estimate that helps the agent make token-budget decisions.

**Service vs inline dispatch**: Using `GetContextService` (mirroring `NoteManagerService`) is the right call here — 5 context_types with distinct logic would make the tool function unreadably long if inlined.
