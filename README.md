# Paddy — Obsidian AI Agent

A self-hosted AI agent that lets you interact with your Obsidian vault using natural language. Chat through the Obsidian Copilot plugin — Paddy reads, writes, searches, and manages your notes on your behalf.

**Local • Private • Provider-agnostic • No database**

## How It Works

```
[You — typing in Obsidian Copilot]
  ↓ natural language
[Obsidian Copilot Plugin]            ← chat UI inside Obsidian
  ↓ POST /v1/chat/completions
[Paddy — FastAPI in Docker :8000]
  ↓ Pydantic AI Agent + LLM
[/vault — Docker volume mount]       ← direct file system, read-write
  ↓
[Your Obsidian Vault — Markdown files]
```

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/basenberg/MyObsidianAgent.git
cd MyObsidianAgent
cp .env.example .env
# Edit .env — set LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, OBSIDIAN_VAULT_PATH, API_KEY

# 2. Start Paddy
docker compose up
```

Point Obsidian Copilot's base URL at `http://localhost:8000` and start chatting.

**Local dev (without Docker):**
```bash
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Prerequisites

**Obsidian Plugins (required):**

| Plugin | Purpose |
|---|---|
| [Obsidian Copilot](https://github.com/logancyang/obsidian-copilot) | Chat UI — set base URL to `http://localhost:8000` |
| Periodic Notes or Daily Notes | Required for daily/weekly/monthly note access |

**System:**
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (local dev only)
- API key for your chosen LLM provider

## What You Can Ask

**Search & Discovery**
> "Find my notes about Python from last month."
> "List everything in my Projects folder."
> "Find all notes tagged #active."

**Reading with Context**
> "Read my architecture decision note and show me related documents."
> "What did I write in my weekly note this week?"
> "Show me today's daily note and all backlinks to it."

**Creating & Managing**
> "Create a new project note for Project X with sections for goals, timeline, and team."
> "Move all meeting notes from last quarter to the archive folder."
> "Tag all notes in the Projects folder with 'active' and add a status field."

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | [Pydantic AI](https://ai.pydantic.dev/) |
| API framework | FastAPI |
| LLM | Provider-agnostic: Anthropic, OpenAI, Google, Ollama |
| Vault access | Docker volume mount (direct file system) |
| Package manager | UV (Astral) |
| Deployment | Docker + Docker Compose |
| Runtime | Python 3.11+ |

## Project Structure

```
project-root/
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
    ├── chat/               # POST /v1/chat/completions
    ├── vault_query/        # obsidian_query_vault tool
    ├── vault_context/      # obsidian_get_context tool
    └── vault_management/   # obsidian_vault_manager tool
```

## Environment Variables

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | LLM provider: `anthropic`, `openai`, `google`, `ollama` |
| `LLM_MODEL` | Model identifier (e.g. `claude-sonnet-4-6`, `gpt-4o`) |
| `LLM_API_KEY` | API key for your chosen provider |
| `OBSIDIAN_VAULT_PATH` | Absolute path to your Obsidian vault on the host |
| `API_KEY` | Bearer token for Obsidian Copilot authentication |
| `API_HOST` | Host to bind (default: `0.0.0.0`) |
| `API_PORT` | Port to bind (default: `8000`) |
| `ALLOWED_ORIGINS` | CORS origins (default: `app://obsidian.md,capacitor://localhost`) |

Docker Compose mounts `OBSIDIAN_VAULT_PATH` as `/vault` inside the container automatically.

## Commands

```bash
# Docker (recommended)
docker compose up
docker compose up --build   # rebuild after dependency changes

# Local development
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Testing
uv run pytest -v                  # all tests
uv run pytest -v -m unit          # unit only
uv run pytest -v -m integration   # integration (vault must be mounted at /vault)

# Type checking
uv run mypy .
uv run pyright .

# Linting
uv run ruff check .
uv run ruff format .
```

## Tools

Paddy exposes **3 consolidated tools** following Anthropic's "fewer, smarter tools" principle:

| Tool | Purpose |
|---|---|
| `obsidian_query_vault` | All discovery, search, and listing (read-only). Supports semantic search, tag/date filtering, folder listing, recent changes, and related note discovery. Token-efficient with `response_format` parameter. |
| `obsidian_get_context` | Workflow-oriented reading. Read single or multiple notes with metadata, backlinks, and related notes compiled for synthesis tasks. |
| `obsidian_vault_manager` | All modification operations: create/update/append/delete/move notes, folder management, and bulk operations (tag, move, update metadata across multiple notes). |

## License

MIT
