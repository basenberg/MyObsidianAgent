# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**Paddy** — Obsidian AI Agent. FastAPI + Pydantic AI, exposed as an OpenAI-compatible endpoint for the Obsidian Copilot plugin. Vault access via Docker volume mount (direct file system, no network plugin required). Provider-agnostic LLM support (Anthropic, OpenAI, Google, Ollama). Python 3.11+.

## Core Principles

**KISS** — Prefer simple, readable solutions over clever abstractions.

**YAGNI** — Don't build features until they're actually needed.

**Vertical Slice Architecture** — Each feature is a self-contained slice under `features/`. Shared utilities go in `shared/` only when used by 3+ features. Core infrastructure (`core/`) is universal.

**Type Safety (CRITICAL)** — Strict MyPy + Pyright enforced. All functions/methods/variables MUST have type annotations. Zero suppressions. No `Any` without explicit justification. Test files have relaxed typing (see pyproject.toml).

## Commands

```bash
# Docker (recommended)
docker compose up
docker compose up --build   # rebuild after dependency changes

# Dev server without Docker (port 8000)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Tests
uv run pytest -v                    # all tests
uv run pytest -v -m unit            # unit only
uv run pytest -v -m integration     # integration only (requires vault mounted at /vault)

# Type checking (must be green)
uv run mypy .
uv run pyright .

# Linting (must be green)
uv run ruff check .
uv run ruff format .
```

## Architecture

### Directory Structure

```
project-root/
├── pyproject.toml          # UV configuration
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── main.py                 # FastAPI entry point
├── core/
│   ├── agent.py            # Single Pydantic AI agent (vault_agent)
│   ├── config.py           # Settings (pydantic-settings)
│   ├── dependencies.py     # VaultDependencies dataclass
│   └── lifespan.py         # FastAPI startup/shutdown
├── shared/
│   ├── vault/
│   │   ├── manager.py      # VaultManager: all file system operations
│   │   └── models.py       # Vault domain models
│   └── openai_adapter.py   # OpenAI format conversion
└── features/
    ├── chat/               # POST /v1/chat/completions (routes.py, models.py)
    ├── vault_query/        # obsidian_query_vault tool (tools.py, models.py)
    ├── vault_context/      # obsidian_get_context tool (tools.py, models.py)
    └── vault_management/   # obsidian_vault_manager tool (tools.py, models.py)
```

### Agent Pattern

Tools register via `@agent.tool` decorator. Each feature imports `vault_agent` from `core/agent.py` and decorates its tool function. `main.py` imports all feature tool modules as side effects to trigger registration.

```python
# core/agent.py — define the agent
vault_agent = Agent('anthropic:claude-sonnet-4-6', deps_type=VaultDependencies)

# features/vault_query/tools.py — register tool
from core.agent import vault_agent

@vault_agent.tool
async def obsidian_query_vault(...):
    pass

# main.py — import to register (side effect)
import features.vault_query.tools  # noqa: F401
```

No circular imports. Message history is stateless per request — Obsidian Copilot sends the full `messages` array each turn.

### Vault Access

Paddy accesses the vault via **Docker volume mount**. The host vault directory is mounted as `/vault` inside the container with read-write permissions. Changes are immediately visible to Obsidian and vice versa. No Obsidian Local REST API plugin required.

### Configuration

Env vars (copy `.env.example` to `.env`):

```bash
LLM_PROVIDER=anthropic              # anthropic | openai | google | ollama
LLM_MODEL=claude-sonnet-4-6        # Model identifier
LLM_API_KEY=sk-...                  # Provider API key
OBSIDIAN_VAULT_PATH=/Users/name/Documents/MyVault  # Host vault path
API_KEY=your-secret-key             # For Obsidian Copilot authentication
API_HOST=0.0.0.0
API_PORT=8000
ALLOWED_ORIGINS=app://obsidian.md,capacitor://localhost
```

Inside the container, the vault is always accessible at `/vault` via volume mount.

## Tools

The agent exposes **3 consolidated tools** following Anthropic's "fewer, smarter tools" principle:

| Tool | Purpose |
|---|---|
| `obsidian_query_vault` | All discovery, search, and listing (read-only): semantic search, tag/date filtering, folder listing, recent changes, related note discovery |
| `obsidian_get_context` | Workflow-oriented reading: single/multiple notes with metadata, backlinks, and related notes compiled for synthesis |
| `obsidian_vault_manager` | All modifications: note CRUD, move, folder management, bulk operations (tag, move, update metadata) |

**Tool naming:** All tools prefixed `obsidian_`, parameters use unambiguous names (`note_path`, `folder_path`, `search_query`).

## Logging

**Philosophy:** Logs are optimized for AI consumption — include enough context for an LLM to understand and fix issues without human intervention.

**Logger:** `from core.logging import get_logger; logger = get_logger(__name__)`

**Event naming:** `{domain}.{component}.{action}_{state}` — e.g., `agent.tool.execution_started`, `vault.notes.read_completed`, `request.http_received`
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
Example: *"Note not found at 'Projects/Foo.md'. Use obsidian_query_vault to list available notes."*

## Testing

Tests mirror the source directory structure. Every file MUST have a corresponding test file.

```
features/vault_query/tools.py   →  tests/features/vault_query/test_tools.py
core/agent.py                   →  tests/core/test_agent.py
shared/vault/manager.py         →  tests/shared/vault/test_manager.py
```

- `@pytest.mark.unit` — isolated, no external dependencies
- `@pytest.mark.integration` — requires vault mounted at `/vault`

## Development Guidelines

**New operations:**
1. Determine which of the 3 tools the operation belongs to (query, context, or management)
2. Add the operation to the appropriate `features/<slice>/tools.py`
3. Update `features/<slice>/models.py` if new types are needed
4. Write the corresponding test file before committing

**Type checking:**
- Run both MyPy and Pyright before committing
- No suppressions (`# type: ignore`, `# pyright: ignore`) unless absolutely necessary — document why inline

**Global rules:** See `~/.claude/CLAUDE.md` — Archon-first task check (Module 10), PIV Loop workflow, slash command templates.
