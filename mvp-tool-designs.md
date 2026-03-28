# MVP Tool Designs — Obsidian AI Agent

## Design Principles

Derived from [Anthropic's guide on writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents).

1. **Design for workflows, not endpoints.** Tools map to how a user thinks about a task, not to underlying API operations.
2. **`obsidian_` prefix on all tools.** Namespacing delineates boundaries when the agent has access to multiple tool sets.
3. **Unambiguous parameter names.** Use `note_path`, `folder_path`, `search_query` — never a bare `path` or `query`.
4. **`response_format` enum on list/search tools.** `"concise"` for navigation (paths only), `"detailed"` for rich context. Keeps token usage low by default.
5. **Actionable error messages.** Errors are steering instructions for the agent, not stack traces.
6. **Plain Python functions.** Tools are pure functions with no knowledge of the agent. `core/agent.py` assembles them (Option B pattern).

---

## Architecture

```
features/
├── notes/
│   └── tools.py     → obsidian_read_note, obsidian_write_note, obsidian_update_note
├── folders/
│   └── tools.py     → obsidian_list_folder, obsidian_create_folder
├── search/
│   └── tools.py     → obsidian_search_vault
├── periodic/
│   └── tools.py     → obsidian_get_periodic_note
└── tasks/
    └── tools.py     → obsidian_get_tasks, obsidian_add_task, obsidian_complete_task
```

All tools call the **Obsidian Local REST API plugin** (`https://localhost:27124`) via an `httpx.AsyncClient` injected through `RunContext[AgentDeps]`. Obsidian must be running with the plugin enabled.

---

## Shared Types

```python
from typing import Literal
from pydantic import BaseModel

ResponseFormat = Literal["concise", "detailed"]

class Task(BaseModel):
    text: str
    done: bool
    line_number: int

class SearchResult(BaseModel):
    note_path: str
    score: float
    context: str  # surrounding content snippet

class FolderItem(BaseModel):
    path: str
    is_folder: bool
    size_bytes: int | None       # None for folders
    modified_at: str | None      # ISO 8601, None for folders
```

---

## Feature: Notes

**File:** `features/notes/tools.py`

### `obsidian_read_note`

```python
async def obsidian_read_note(
    ctx: RunContext[AgentDeps],
    note_path: str,
) -> str:
    """
    Read the full Markdown content of a note from the Obsidian vault.

    note_path: Vault-relative path to the note, e.g. "Daily Notes/2025-03-27.md".
               Include the .md extension.

    Returns the raw Markdown text of the note.

    Errors:
    - If the note does not exist, returns a clear message with the attempted path
      so you can verify the path using obsidian_list_folder first.
    """
```

---

### `obsidian_write_note`

```python
async def obsidian_write_note(
    ctx: RunContext[AgentDeps],
    note_path: str,
    content: str,
) -> str:
    """
    Create a new note or fully overwrite an existing note in the Obsidian vault.

    note_path: Vault-relative path including filename, e.g. "Projects/MyProject.md".
               Parent folders are created automatically if they do not exist.
    content:   Full Markdown content to write. Include YAML frontmatter if needed.

    Use obsidian_update_note instead if you only want to append or insert content
    without replacing the full note.

    Returns a confirmation message with the path written.
    """
```

---

### `obsidian_update_note`

```python
async def obsidian_update_note(
    ctx: RunContext[AgentDeps],
    note_path: str,
    content: str,
    mode: Literal["append", "prepend"] = "append",
    target_heading: str | None = None,
) -> str:
    """
    Add content to an existing note without replacing it.

    note_path:      Vault-relative path to the note, e.g. "Projects/MyProject.md".
    content:        Markdown text to insert.
    mode:           "append" adds content after the target (default).
                    "prepend" adds content before the target.
    target_heading: Optional. Scope the insertion to a specific heading, e.g. "## Tasks".
                    If omitted, content is added at the very end (append) or beginning
                    (prepend) of the note.

    Use obsidian_write_note if you need to replace the entire note content.

    Returns a confirmation message with the location updated.
    """
```

---

## Feature: Folders

**File:** `features/folders/tools.py`

### `obsidian_list_folder`

```python
async def obsidian_list_folder(
    ctx: RunContext[AgentDeps],
    folder_path: str = "",
    response_format: ResponseFormat = "concise",
) -> list[str] | list[FolderItem]:
    """
    List the contents of a folder in the Obsidian vault.

    folder_path:     Vault-relative path to the folder, e.g. "Projects" or "Daily Notes".
                     Use "" (empty string) for the vault root.
    response_format: "concise" returns a list of path strings (default, low token cost).
                     "detailed" returns FolderItem objects with path, is_folder,
                     size_bytes, and modified_at fields.

    Use "concise" when navigating the vault structure.
    Use "detailed" when you need to sort by date or filter by file size.

    Returns only the immediate children — not recursive. Call obsidian_list_folder
    again on a subfolder to drill down.
    """
```

---

### `obsidian_create_folder`

```python
async def obsidian_create_folder(
    ctx: RunContext[AgentDeps],
    folder_path: str,
) -> str:
    """
    Create a new folder in the Obsidian vault.

    folder_path: Vault-relative path for the new folder, e.g. "Projects/2025".
                 Nested paths are created in full — no need to create parent folders first.

    If the folder already exists, returns a confirmation without error.

    Returns a confirmation message with the folder path created.
    """
```

---

## Feature: Search

**File:** `features/search/tools.py`

### `obsidian_search_vault`

```python
async def obsidian_search_vault(
    ctx: RunContext[AgentDeps],
    search_query: str,
    response_format: ResponseFormat = "concise",
    context_length: int = 200,
) -> list[str] | list[SearchResult]:
    """
    Search all notes in the Obsidian vault by content.

    search_query:    Plain-text search term. Searches note content and filenames.
                     Be specific — broad queries return many low-relevance results.
    response_format: "concise" returns a list of matching note paths (default).
                     "detailed" returns SearchResult objects with note_path, relevance
                     score, and a content snippet around each match.
    context_length:  Characters of surrounding context to include per match when
                     response_format is "detailed". Default: 200.

    If results are truncated, narrow your search_query with more specific terms.

    Returns results ordered by relevance score, highest first.
    """
```

---

## Feature: Periodic Notes

**File:** `features/periodic/tools.py`

### `obsidian_get_periodic_note`

```python
async def obsidian_get_periodic_note(
    ctx: RunContext[AgentDeps],
    period: Literal["daily", "weekly", "monthly", "quarterly", "yearly"] = "daily",
) -> str:
    """
    Get the content of the current periodic note from the Obsidian vault.

    period: Which periodic note to retrieve.
            "daily"     — today's daily note (default)
            "weekly"    — this week's weekly note
            "monthly"   — this month's monthly note
            "quarterly" — this quarter's note
            "yearly"    — this year's note

    Requires the Periodic Notes or Daily Notes plugin to be enabled in Obsidian.
    Returns the full Markdown content of the note.

    To update the daily note, use obsidian_update_note with the path returned
    by this tool, or use obsidian_add_task to append a task directly.
    """
```

---

## Feature: Tasks

**File:** `features/tasks/tools.py`

### `obsidian_get_tasks`

```python
async def obsidian_get_tasks(
    ctx: RunContext[AgentDeps],
    note_path: str,
) -> list[Task]:
    """
    Extract all tasks (checkboxes) from a note in the Obsidian vault.

    note_path: Vault-relative path to the note, e.g. "Daily Notes/2025-03-27.md".

    Returns a list of Task objects, each with:
    - text:        The task description (e.g. "Write project proposal")
    - done:        True if the task is checked [x], False if open [ ]
    - line_number: 1-based line number in the note for reference

    Both open and completed tasks are returned. Filter on the `done` field
    if you only need open tasks.
    """
```

---

### `obsidian_add_task`

```python
async def obsidian_add_task(
    ctx: RunContext[AgentDeps],
    note_path: str,
    task_text: str,
    target_heading: str | None = None,
) -> str:
    """
    Add a new open task to a note in the Obsidian vault.

    note_path:      Vault-relative path to the note, e.g. "Daily Notes/2025-03-27.md".
    task_text:      The task description. Do not include the checkbox — it is added
                    automatically. Example: "Review meeting notes"
    target_heading: Optional. Insert the task under a specific heading, e.g. "## Tasks".
                    If omitted, the task is appended to the end of the note.

    Returns a confirmation message with the task added and its location.
    """
```

---

### `obsidian_complete_task`

```python
async def obsidian_complete_task(
    ctx: RunContext[AgentDeps],
    note_path: str,
    task_text: str,
) -> str:
    """
    Mark an open task as complete in a note in the Obsidian vault.

    note_path: Vault-relative path to the note, e.g. "Daily Notes/2025-03-27.md".
    task_text: The task description to match. Uses a case-insensitive substring match —
               you do not need to provide the exact full text, but be specific enough
               to avoid ambiguous matches.

    If multiple tasks match task_text, returns a list of matches and asks you to
    be more specific. If no tasks match, returns a clear message so you can verify
    using obsidian_get_tasks first.

    Returns a confirmation message with the task marked complete.
    """
```

---

## Tool Inventory Summary

| # | Tool | Feature | Key Parameters |
|---|---|---|---|
| 1 | `obsidian_read_note` | notes | `note_path` |
| 2 | `obsidian_write_note` | notes | `note_path`, `content` |
| 3 | `obsidian_update_note` | notes | `note_path`, `content`, `mode`, `target_heading?` |
| 4 | `obsidian_list_folder` | folders | `folder_path`, `response_format` |
| 5 | `obsidian_create_folder` | folders | `folder_path` |
| 6 | `obsidian_search_vault` | search | `search_query`, `response_format`, `context_length?` |
| 7 | `obsidian_get_periodic_note` | periodic | `period` |
| 8 | `obsidian_get_tasks` | tasks | `note_path` |
| 9 | `obsidian_add_task` | tasks | `note_path`, `task_text`, `target_heading?` |
| 10 | `obsidian_complete_task` | tasks | `note_path`, `task_text` |

**10 tools across 5 feature slices.**

---

## Deferred (Post-MVP)

| Tool | Reason Deferred |
|---|---|
| `obsidian_delete_note` | Destructive — needs confirmation UX and recycle bin strategy |
| `obsidian_batch_read_notes` | Useful for context gathering; agent can call `obsidian_read_note` in sequence for MVP |
| `obsidian_get_recent_changes` | Requires Dataview DQL — additional plugin dependency |
| `obsidian_get_recent_periodic_notes` | Defer until periodic notes are proven stable in MVP |
| `obsidian_complex_search` | JsonLogic query construction is too complex for MVP; plain search covers most cases |
| Tag management | No stable API support from Local REST API plugin |
