# Paddy — Obsidian AI Agent

A locally-hosted AI agent that connects to your Obsidian vault via natural language. Interact through the Obsidian Copilot chat panel — Paddy reads, writes, searches, and manages your notes and tasks on your behalf.

**Local • Private • No database**

## How It Works

```
[You — typing in Obsidian Copilot]
  ↓ natural language
[Obsidian Copilot Plugin]        ← chat UI inside Obsidian
  ↓ POST /v1/chat/completions
[Paddy — FastAPI on localhost:8000]
  ↓ Pydantic AI Agent + Claude
[Obsidian Local REST API Plugin] ← vault access (localhost:27124)
  ↓
[Your Obsidian Vault — Markdown files]
```

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/basenberg/MyObsidianAgent.git
cd dynamous-community\MyObsidianAgent
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY, OBSIDIAN_API_KEY, OBSIDIAN_VAULT_PATH

# 3. Start Obsidian with Local REST API plugin active

# 4. Run Paddy
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Point Obsidian Copilot's base URL at `http://localhost:8000` and start chatting.

## Prerequisites

**Obsidian Plugins (required):**

| Plugin | Purpose |
|---|---|
| [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) | Exposes vault over HTTPS on `localhost:27124` |
| [Obsidian Copilot](https://github.com/logancyang/obsidian-copilot) | Chat UI — set base URL to `http://localhost:8000` |
| Periodic Notes or Daily Notes | Required for daily/weekly/monthly note access |

**System:**
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Anthropic API key

## What You Can Ask

**Tasks**
> "What tasks do I have open in my project notes?"
> "Mark the API design task as complete in my Sprint notes."
> "Add a task to follow up with the client under Action Items."

**Notes**
> "Create a new project note for Project X with a standard template."
> "What did I write in my weekly note this week?"
> "Search my vault for everything related to the Acme project."

**Navigation**
> "List everything in my Projects folder."
> "Find all notes that mention the word 'deadline'."
> "Read my daily note for today."

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | [Pydantic AI](https://ai.pydantic.dev/) |
| API framework | FastAPI |
| LLM | Claude (Anthropic API) |
| Vault access | Obsidian Local REST API (httpx) |
| Package manager | UV (Astral) |
| Runtime | Python 3.12+ |

## Project Structure

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
│   ├── chat/               # POST /v1/chat/completions
│   ├── notes/              # Read, write, update notes
│   ├── folders/            # List, create folders
│   ├── search/             # Full-text vault search
│   ├── periodic/           # Daily/weekly/monthly notes
│   └── tasks/              # View, add, complete tasks
└── main.py
```

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OBSIDIAN_API_KEY` | Bearer token from Local REST API plugin settings |
| `OBSIDIAN_VAULT_PATH` | Absolute path to your Obsidian vault |
| `OBSIDIAN_API_URL` | Local REST API base URL (default: `https://localhost:27124`) |
| `LLM_MODEL` | Claude model ID (default: `claude-sonnet-4-6`) |

## Commands

```bash
# Development
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Testing
uv run pytest -v                  # all tests
uv run pytest -v -m unit          # unit only
uv run pytest -v -m integration   # integration (Obsidian must be running)

# Type checking
uv run mypy app/
uv run pyright app/

# Linting
uv run ruff check .
uv run ruff format .
```

## MVP Tool Set

All tools are prefixed `obsidian_` with unambiguous parameter names.

| Tool | Purpose |
|---|---|
| `obsidian_read_note` | Read full note content |
| `obsidian_write_note` | Create or overwrite a note |
| `obsidian_update_note` | Append/prepend, optionally scoped to a heading |
| `obsidian_list_folder` | List folder contents |
| `obsidian_create_folder` | Create a new folder |
| `obsidian_search_vault` | Full-text search across all notes |
| `obsidian_get_periodic_note` | Get current daily/weekly/monthly note |
| `obsidian_get_tasks` | Extract structured task list from a note |
| `obsidian_add_task` | Add a task, optionally under a heading |
| `obsidian_complete_task` | Mark a matching task as complete |

## License

MIT
