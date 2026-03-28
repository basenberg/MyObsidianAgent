# PRD — Obsidian AI Agent

## Executive Summary

A locally-hosted AI agent that connects to an Obsidian vault via natural language. Users interact through the Obsidian Copilot plugin; the agent reads, writes, searches, and manages notes and tasks on their behalf. Built on FastAPI and Pydantic AI, exposed as an OpenAI-compatible API endpoint.

---

## Mission

Enable Obsidian vault users to manage their notes, tasks, and projects through natural language — reducing friction and making their vault more actionable.

---

## Target User

**Primary:** A single Obsidian power user who:
- Maintains an active vault for task tracking and project management
- Wants to query, update, and organize their vault without manual navigation
- Is comfortable running a local Python server alongside Obsidian

---

## Problem Statement

Obsidian is a powerful knowledge tool, but interacting with it is always manual — opening files, navigating folders, editing checkboxes. There is no way to ask your vault a question, delegate a task update, or create structured notes through conversation. The vault becomes harder to maintain as it grows.

---

## Solution

An AI agent that sits alongside Obsidian and acts as an intelligent interface to the vault. The user types a natural language request in the Obsidian Copilot chat panel; the agent interprets it, calls the appropriate tools against the vault, and responds with results or confirmation.

---

## MVP Scope

### In Scope

- Natural language read/write access to vault notes
- Task management: view, add, and complete checkbox tasks within notes
- Folder navigation and creation
- Full-text vault search
- Daily/periodic note access
- Single-user, local deployment
- OpenAI-compatible chat endpoint (compatible with Obsidian Copilot plugin)
- Claude as the LLM backend (Anthropic API)

### Out of Scope (Post-MVP)

- Multi-user or multi-vault support
- Note deletion (deferred — requires confirmation UX)
- Tag management
- Complex metadata queries (Dataview DQL, JsonLogic)
- Semantic/vector search
- Hosted or SaaS deployment
- Voice interface

---

## Priority Use Cases

### 1. Task Tracking
> "What tasks do I have open in my project notes?"
> "Mark the API design task as complete in my Sprint notes."
> "Add a task to follow up with the client under the ## Action Items heading."

### 2. Project Management
> "Create a new project note for Project X with a standard template."
> "Search my vault for everything related to the Acme project."
> "What did I write in my weekly note this week?"

### 3. Vault Navigation
> "List everything in my Projects folder."
> "Find all notes that mention the word 'deadline'."
> "Read my daily note for today."

---

## Architecture

### System Overview

```
[User]
  ↓ natural language
[Obsidian Copilot Plugin]        ← frontend (chat UI inside Obsidian)
  ↓ POST /v1/chat/completions
[FastAPI Backend — localhost:8000]
  ↓ Pydantic AI Agent
[Obsidian Local REST API Plugin] ← vault access layer (localhost:27124)
  ↓
[Obsidian Vault — Markdown files]
```

### Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | Pydantic AI |
| API framework | FastAPI |
| LLM | Claude (Anthropic API) |
| Vault access | Obsidian Local REST API plugin (httpx) |
| Frontend | Obsidian Copilot plugin |
| Package manager | UV (Astral) |
| Runtime | Python 3.12+ |

### Project Structure

```
app/                           ← Python project root (run uv from here)
├── pyproject.toml
├── main.py                    ← FastAPI app
├── core/
│   ├── config.py              ← settings: vault path, API keys, LLM model
│   ├── agent.py               ← Agent factory: assembles tools → Agent
│   ├── obsidian_client.py     ← httpx.AsyncClient for Local REST API
│   └── deps.py                ← AgentDeps dataclass
├── shared/
│   └── openai_schema.py       ← OpenAI-compatible request/response models
└── features/
    ├── chat/
    │   ├── routes.py          ← POST /v1/chat/completions
    │   └── service.py         ← agent runner, message history
    ├── notes/
    │   └── tools.py
    ├── folders/
    │   └── tools.py
    ├── search/
    │   └── tools.py
    ├── periodic/
    │   └── tools.py
    └── tasks/
        └── tools.py
```

### Architecture Pattern

**Vertical Slice Architecture (VSA).** Each feature is a self-contained slice. `core/` holds universal infrastructure only. Features are independent — removing one has no impact on others.

**Tool Assembly (Option B).** Feature tools are plain Python functions with no knowledge of the agent. `core/agent.py` collects all tool functions and passes them to `Agent(tools=[...])`. No circular imports.

---

## Core Patterns

### OpenAI-Compatible Endpoint

The `/v1/chat/completions` endpoint accepts the standard OpenAI chat request format. This makes the backend plug-and-play with Obsidian Copilot and any other OpenAI-compatible client without modification.

### Message History

Conversation history is stateless per HTTP request. The Obsidian Copilot plugin sends the full `messages` array on each turn. The agent passes this to Pydantic AI's `message_history` parameter. No server-side session storage in MVP.

### Dependency Injection

Tools receive vault access via `RunContext[AgentDeps]`. `AgentDeps` holds the `ObsidianClient` instance. FastAPI injects the client per request via `Depends`.

### Response Format Enum

List and search tools expose a `response_format: Literal["concise", "detailed"]` parameter. `"concise"` returns paths only (low token cost). `"detailed"` returns rich metadata. Default is always `"concise"`.

### Actionable Error Messages

Tool errors are written as steering instructions for the agent, not exception messages. Example: *"Note not found at 'Projects/Foo.md'. Use obsidian_list_folder to verify the path."*

---

## MVP Tool Set

All tools are prefixed with `obsidian_`. Parameters use unambiguous names (`note_path`, `folder_path`, `search_query`).

| # | Tool | Feature | Purpose |
|---|---|---|---|
| 1 | `obsidian_read_note` | notes | Read full note content |
| 2 | `obsidian_write_note` | notes | Create or overwrite a note |
| 3 | `obsidian_update_note` | notes | Append/prepend to a note, optionally scoped to a heading |
| 4 | `obsidian_list_folder` | folders | List folder contents (concise or detailed) |
| 5 | `obsidian_create_folder` | folders | Create a new folder |
| 6 | `obsidian_search_vault` | search | Full-text search across all notes |
| 7 | `obsidian_get_periodic_note` | periodic | Get current daily/weekly/monthly note |
| 8 | `obsidian_get_tasks` | tasks | Extract structured task list from a note |
| 9 | `obsidian_add_task` | tasks | Add a new task, optionally under a heading |
| 10 | `obsidian_complete_task` | tasks | Mark a matching task as complete |

Full tool designs and docstrings: `mvp-tool-designs.md`

---

## Required Obsidian Plugins

| Plugin | Role |
|---|---|
| **Local REST API** (`coddingtonbear/obsidian-local-rest-api`) | Exposes vault over HTTPS on localhost:27124. Required for all agent tool calls. |
| **Obsidian Copilot** (`logancyang/obsidian-copilot`) | Chat UI frontend. Point base URL at `http://localhost:8000`. |
| **Periodic Notes** or **Daily Notes** | Required for `obsidian_get_periodic_note` to work. |

---

## Deployment

### Local (MVP)

```bash
cd app
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Obsidian must be running with Local REST API plugin active.

### Docker (Future)

The backend is stateless and portable. A `Dockerfile` and `docker-compose.yml` can be added post-MVP. The vault path would be mounted as a volume. The agent can fall back to direct filesystem access when Obsidian is not running.

---

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `OBSIDIAN_API_KEY` | Bearer token from Local REST API plugin settings |
| `OBSIDIAN_VAULT_PATH` | Absolute path to the Obsidian vault on disk |
| `OBSIDIAN_API_URL` | Local REST API base URL (default: `https://localhost:27124`) |
| `LLM_MODEL` | Claude model ID (default: `claude-sonnet-4-6`) |

---

## Success Metrics (MVP)

- User can ask a natural language question and receive a correct vault response
- User can create, update, and search notes without touching the Obsidian UI
- User can view and complete tasks via chat
- Agent correctly selects tools without requiring explicit tool names from the user
- Response latency under 5 seconds for single-tool calls on local hardware
