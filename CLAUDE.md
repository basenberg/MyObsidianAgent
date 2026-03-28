# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Obsidian AI Agent — FastAPI + Pydantic AI, exposed as an OpenAI-compatible endpoint for the Obsidian Copilot plugin. No database; vault access via Obsidian Local REST API (httpx). Claude (Anthropic API) as LLM. Python 3.12+.

## Core Principles

**KISS** — Prefer simple, readable solutions over clever abstractions.

**YAGNI** — Don't build features until they're actually needed.

**Vertical Slice Architecture** — Each feature is a self-contained slice under `app/features/`. Shared utilities go in `app/shared/` only when used by 3+ features. Core infrastructure (`app/core/`) is universal.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions/methods/variables MUST have type annotations. Zero suppressions. No `Any` without explicit justification. Test files have relaxed typing (see pyproject.toml).

## Commands

```bash
# Dev server (port 8000)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Tests
uv run pytest -v                    # all tests
uv run pytest -v -m unit            # unit only
uv run pytest -v -m integration     # integration only (requires Obsidian REST API running)

# Type checking (must be green)
uv run mypy app/
uv run pyright app/

# Linting (must be green)
uv run ruff check .
uv run ruff format .
```

## Architecture

### Directory Structure

```
app/
├── core/
│   ├── config.py           # Settings: vault path, API keys, LLM model
│   ├── agent.py            # Agent factory: assembles tools → Agent
│   ├── obsidian_client.py  # httpx.AsyncClient for Obsidian Local REST API
│   ├── logging.py          # Structlog setup
│   └── deps.py             # AgentDeps dataclass
├── shared/
│   └── openai_schema.py    # OpenAI-compatible request/response models
├── features/
│   ├── chat/               # POST /v1/chat/completions (routes.py, service.py)
│   ├── notes/              # tools.py
│   ├── folders/            # tools.py
│   ├── search/             # tools.py
│   ├── periodic/           # tools.py
│   └── tasks/              # tools.py
└── main.py
```

### Agent Pattern

Feature tools are plain Python functions with no knowledge of the agent. `core/agent.py` collects all tool functions and passes them to `Agent(tools=[...])`. No circular imports. Message history is stateless per request — Obsidian Copilot sends full `messages` array each turn.

### Configuration

Env vars: `ANTHROPIC_API_KEY`, `OBSIDIAN_API_KEY`, `OBSIDIAN_VAULT_PATH`, `OBSIDIAN_API_URL` (default: `https://localhost:27124`), `LLM_MODEL` (default: `claude-sonnet-4-6`). Copy `.env.example` to `.env`.

## Logging

**Philosophy:** Logs are optimized for AI consumption — include enough context for an LLM to understand and fix issues without human intervention.

**Logger:** `from app.core.logging import get_logger; logger = get_logger(__name__)`

**Event naming:** `{domain}.{component}.{action}_{state}` — e.g., `agent.tool.execution_started`, `obsidian.notes.read_completed`, `request.http_received`
- States: `_started`, `_completed`, `_failed`, `_validated`, `_rejected`

**Required:**
- Keyword args only — never string formatting: `logger.info("agent.tool.started", tool=name)` ✓
- `logger.exception()` in except blocks — captures full stack trace automatically
- Include context: IDs, `duration_ms`, `fix_suggestion` on errors for AI self-correction
- Do NOT log sensitive data (API keys, tokens — mask: `key[:8] + "..."`)
- Do NOT silently catch exceptions

```python
# Tool execution pattern
logger.info("agent.tool.execution_started", tool=name, params=params)
result = await tool.execute(params)
logger.info("agent.tool.execution_completed", tool=name, duration_ms=elapsed)

# Error pattern
except ToolError:
    logger.exception("agent.tool.execution_failed", tool=name,
                     fix_suggestion="Check tool parameters or retry with different values")
    raise
```

## Documentation Style

**Google-style docstrings** for all functions and classes.

**Agent tool docstrings** must guide LLM tool selection, not just document behavior:
1. Guide tool selection — when to use this tool vs alternatives
2. Prevent token waste — steer toward efficient parameter choices
3. Enable composition — show how the tool fits multi-step workflows
4. Set expectations — performance characteristics and limitations
5. Provide concrete examples with realistic data

**Actionable error messages:** Write tool errors as agent steering instructions, not exception text.
Example: *"Note not found at 'Projects/Foo.md'. Use obsidian_list_folder to verify the path."*

## Testing

Tests mirror the source directory structure. Every file in `app/` MUST have a corresponding test file.

```
app/features/notes/tools.py  →  tests/features/notes/test_tools.py
app/core/agent.py            →  tests/core/test_agent.py
```

- `@pytest.mark.unit` — isolated, no external dependencies
- `@pytest.mark.integration` — requires Obsidian Local REST API running

## Development Guidelines

**New features:**
1. Create slice under `app/features/` with `tools.py` (add `schemas.py` if needed)
2. Register tools in `core/agent.py`: `Agent(tools=[..., new_tool])`
3. All tools prefixed `obsidian_`, parameters use unambiguous names (`note_path`, `folder_path`, `search_query`)
4. Write the corresponding test file before committing

**Type checking:**
- Run both MyPy and Pyright before committing
- No suppressions (`# type: ignore`, `# pyright: ignore`) unless absolutely necessary — document why inline

**Global rules:** See `~/.claude/CLAUDE.md` — Archon-first task check (Module 10), PIV Loop workflow, slash command templates.
