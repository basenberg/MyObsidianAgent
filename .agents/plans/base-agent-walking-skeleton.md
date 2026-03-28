# Feature: Base Agent Walking Skeleton

## Feature Description

Bootstrap the Pydantic AI `vault_agent` with a simple prompt, expose it via `POST /v1/chat/completions`,
and establish the root-level `tests/` directory. Result: a thin end-to-end slice proving
Obsidian Copilot → FastAPI → Pydantic AI → response works before vault tooling is added.

## User Story

As a developer, I want to POST a chat message to `/v1/chat/completions` and receive a valid
OpenAI-format response, so I can verify the full request path works before building vault tools.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/core/agent/`, `app/features/chat/`, `app/shared/`, `app/core/config.py`
**Dependencies**: `pydantic-ai`, `anthropic`, `python-dotenv`

---

## CONTEXT REFERENCES

### Files to Read Before Implementing

- `app/core/config.py` — Settings pattern, `@lru_cache`, `SettingsConfigDict`, `type: ignore[call-arg]`
- `app/core/logging.py` — `get_logger(__name__)`, keyword-args-only logging
- `app/core/middleware.py` — Module-level logger pattern
- `app/core/exceptions.py` — `cast(Any, ...)` pattern, exception handler setup
- `app/main.py` — Lifespan, router inclusion, existing wiring
- `app/core/tests/test_config.py` — `patch.dict(os.environ, ...)` pattern; tests to update
- `app/tests/test_main.py` — `TestClient(app)` fixture pattern
- `docs/logging-standard.md` — Agent domain events: `agent.lifecycle.*`, `agent.llm.*`
- `docs/pytest-standard.md` — Marker config, async test patterns
- `docs/mypy-standard.md` — Strict typing rules, `type: ignore` documentation

### New Files to Create

```
app/core/agent/__init__.py          re-exports vault_agent
app/core/agent/types.py             type aliases
app/core/agent/dependencies.py      AgentDependencies dataclass
app/core/agent/agent.py             vault_agent singleton
app/shared/openai_adapter.py        OpenAI ↔ Pydantic AI conversion
app/features/__init__.py
app/features/chat/__init__.py
app/features/chat/models.py         ChatRequest, ChatResponse, etc.
app/features/chat/routes.py         POST /v1/chat/completions
tests/__init__.py
tests/conftest.py                   app_client fixture + test_env_vars
tests/core/__init__.py
tests/core/agent/__init__.py
tests/core/agent/test_agent.py
tests/features/__init__.py
tests/features/chat/__init__.py
tests/features/chat/test_routes.py
```

### Files to Update

- `app/core/config.py` — Add LLM fields; python-dotenv load; make `database_url` optional
- `app/core/tests/test_config.py` — Remove required `DATABASE_URL` patches; add LLM field tests
- `app/main.py` — Add chat router; guard `engine.dispose()` for optional DB
- `.env.example` — Add LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, API_KEY; comment DATABASE_URL
- `pyproject.toml` — Add `unit` marker to pytest markers

### Patterns to Follow

```python
# Module-level logger (middleware.py:20)
logger = get_logger(__name__)

# Logging — keyword args only, never f-strings (logging-standard.md)
logger.info("agent.lifecycle.initialized", model=model_string, provider=settings.llm_provider)
logger.error("agent.llm.call_failed", error=str(e), exc_info=True)

# Settings (config.py:45-60)
@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

# Test env patch (test_config.py:25)
with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}):
    get_settings.cache_clear()
    settings = create_settings()
```

---

## STEP-BY-STEP TASKS

### TASK 1 — INSTALL dependencies

```bash
uv add pydantic-ai anthropic python-dotenv
```

- **VALIDATE**: `uv run python -c "import pydantic_ai; import anthropic; import dotenv; print('ok')"`

---

### TASK 2 — UPDATE `pyproject.toml`

Add `unit` marker alongside the existing `integration` marker:

```toml
"unit: marks fast isolated unit tests with no external dependencies",
```

- **VALIDATE**: `uv run pytest --co -q 2>&1 | head -5`

---

### TASK 3 — UPDATE `app/core/config.py`

Add `from dotenv import load_dotenv; load_dotenv()` at module top. Add fields to `Settings`:

```python
# LLM
llm_provider: str = "anthropic"
llm_model: str = "claude-haiku-4-5-20251001"
llm_api_key: str = ""

# Auth
api_key: str = ""

# Database — optional, not required for agent-only deployments
database_url: str = ""
```

- **GOTCHA**: `database_url` changes from required to optional — existing tests that patch `DATABASE_URL` still work but the patch is no longer required
- **VALIDATE**: `uv run python -c "from app.core.config import get_settings; get_settings.cache_clear(); print(get_settings().llm_model)"`

---

### TASK 4 — UPDATE `.env.example`

```bash
# LLM
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
LLM_API_KEY=sk-ant-...

# Auth
API_KEY=your-secret-api-key

# Database (optional)
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/obsidian_db
```

---

### TASK 5 — UPDATE `app/core/tests/test_config.py`

- Remove `DATABASE_URL` from all `patch.dict` calls (it now has a default)
- Call `get_settings.cache_clear()` at start of each test
- Add two new tests:

```python
@pytest.mark.unit
def test_llm_settings_defaults() -> None:
    get_settings.cache_clear()
    settings = create_settings()
    assert settings.llm_provider == "anthropic"
    assert settings.llm_model == "claude-haiku-4-5-20251001"

@pytest.mark.unit
def test_llm_settings_from_environment() -> None:
    with patch.dict(os.environ, {
        "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o",
        "LLM_API_KEY": "sk-test", "API_KEY": "my-key",
    }):
        get_settings.cache_clear()
        settings = create_settings()
        assert settings.llm_provider == "openai"
        assert settings.api_key == "my-key"
```

- **VALIDATE**: `uv run pytest app/core/tests/test_config.py -v`

---

### TASK 6 — CREATE `app/core/agent/types.py`

```python
"""Type definitions for the core agent module."""
from typing import TypeAlias

ModelString: TypeAlias = str
MessageContent: TypeAlias = str
```

---

### TASK 7 — CREATE `app/core/agent/dependencies.py`

```python
"""Agent dependency injection container."""
from dataclasses import dataclass


@dataclass
class AgentDependencies:
    """Dependencies injected into vault_agent via RunContext.

    Attributes:
        request_id: HTTP request correlation ID.
    """
    request_id: str = ""
```

---

### TASK 8 — CREATE `app/core/agent/agent.py`

```python
"""Pydantic AI vault agent singleton."""
from pydantic_ai import Agent

from app.core.agent.dependencies import AgentDependencies
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
_model_string: str = f"{settings.llm_provider}:{settings.llm_model}"

vault_agent: Agent[AgentDependencies, str] = Agent(
    _model_string,
    deps_type=AgentDependencies,
    instructions=(
        "You are Paddy, an AI assistant for an Obsidian knowledge vault. "
        "Help the user query, read, and manage their notes. "
        "Be concise. When tools are available, prefer them over guessing."
    ),
)

logger.info("agent.lifecycle.initialized", model=_model_string, provider=settings.llm_provider)
```

- **GOTCHA**: Use `instructions=` not `system_prompt=` — instructions are excluded from stored history, correct for stateless per-request usage
- **GOTCHA**: `Agent[AgentDependencies, str]` explicit generic required for Pyright strict mode
- **VALIDATE**: `uv run python -c "from app.core.agent.agent import vault_agent; print(vault_agent)"`

---

### TASK 9 — CREATE `app/core/agent/__init__.py`

```python
"""Core agent package."""
from app.core.agent.agent import vault_agent

__all__ = ["vault_agent"]
```

---

### TASK 10 — CREATE `app/shared/openai_adapter.py`

```python
"""Bridge between OpenAI message format and Pydantic AI internals."""
import time
import uuid

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.features.chat.models import ChatMessage, ChatResponse, Choice, ResponseMessage, UsageInfo


def extract_user_prompt(messages: list[ChatMessage]) -> str:
    """Return the last user message content.

    Raises:
        ValueError: If no user message exists in messages.
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise ValueError("No user message found in messages list.")


def to_pydantic_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert all messages except the last user message to Pydantic AI format."""
    history: list[ModelMessage] = []
    # Exclude the last user message (it becomes the user_prompt arg)
    msgs = messages[:-1] if messages and messages[-1].role == "user" else messages
    for msg in msgs:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant":
            history.append(
                ModelResponse(
                    parts=[TextPart(content=msg.content)],
                    model_name="paddy",
                    timestamp=None,  # type: ignore[arg-type]
                )
            )
    return history


def to_openai_response(content: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> ChatResponse:
    """Wrap agent output in OpenAI chat completion shape."""
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4()}",
        created=int(time.time()),
        choices=[Choice(message=ResponseMessage(content=content))],
        usage=UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
```

- **GOTCHA**: Verify `pydantic_ai.messages` export names after install: `uv run python -c "import pydantic_ai.messages; print(dir(pydantic_ai.messages))"`
- **VALIDATE**: `uv run mypy app/shared/openai_adapter.py`

---

### TASK 11 — CREATE `app/features/chat/models.py`

```python
"""Pydantic models for OpenAI-compatible chat completion API."""
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "paddy"
    messages: list[ChatMessage]
    stream: bool = False


class ResponseMessage(BaseModel):
    role: str = "assistant"
    content: str


class Choice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "paddy"
    choices: list[Choice]
    usage: UsageInfo
```

---

### TASK 12 — CREATE `app/features/chat/routes.py`

```python
"""POST /v1/chat/completions — OpenAI-compatible chat endpoint."""
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.config import get_settings
from app.core.logging import get_logger, get_request_id
from app.features.chat.models import ChatRequest, ChatResponse
from app.shared.openai_adapter import extract_user_prompt, to_openai_response, to_pydantic_history

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validate Bearer token against API_KEY setting.

    Raises:
        HTTPException: 401 if token is invalid.
    """
    if credentials.token != get_settings().api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return credentials.token


@router.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
) -> ChatResponse:
    """Handle OpenAI-compatible chat completion requests."""
    logger.info("request.chat_received", message_count=len(request.messages))

    user_prompt = extract_user_prompt(request.messages)
    history = to_pydantic_history(request.messages)
    deps = AgentDependencies(request_id=get_request_id())

    start = time.time()
    logger.info("agent.llm.call_started", prompt_length=len(user_prompt))

    result = await vault_agent.run(user_prompt, deps=deps, message_history=history)

    usage = result.usage()
    logger.info(
        "agent.llm.call_completed",
        duration_ms=round((time.time() - start) * 1000, 2),
        tokens_prompt=usage.request_tokens,
        tokens_completion=usage.response_tokens,
    )

    return to_openai_response(result.output, usage.request_tokens, usage.response_tokens)
```

- **GOTCHA**: `_api_key` underscore prefix satisfies ruff `ARG` rule for unused Depends args
- **GOTCHA**: `usage.request_tokens` / `usage.response_tokens` — verify field names against installed pydantic-ai version
- **VALIDATE**: `uv run mypy app/features/chat/routes.py`

---

### TASK 13 — UPDATE `app/main.py`

Add import and router registration. Guard DB disposal:

```python
# Add import
from app.features.chat import routes as chat_routes

# After health_router inclusion:
app.include_router(chat_routes.router)

# In lifespan shutdown, replace engine.dispose() with:
if settings.database_url:
    await engine.dispose()
    logger.info("database.connection_closed")
```

- **VALIDATE**: `uv run python -c "from app.main import app; print([r.path for r in app.routes])"`

---

### TASK 14 — CREATE `tests/conftest.py` and package `__init__.py` files

Create empty `__init__.py` in: `tests/`, `tests/core/`, `tests/core/agent/`, `tests/features/`, `tests/features/chat/`

`tests/conftest.py`:

```python
"""Shared fixtures for root tests/ directory."""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_env_vars() -> dict[str, str]:
    return {
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-haiku-4-5-20251001",
        "LLM_API_KEY": "test-key-not-real",
        "API_KEY": "test-bearer-token",
    }


@pytest.fixture
def app_client(test_env_vars: dict[str, str]) -> TestClient:
    from app.core.config import get_settings
    from app.main import app
    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        yield TestClient(app)
    get_settings.cache_clear()
```

- **VALIDATE**: `uv run pytest tests/ --co -q`

---

### TASK 15 — CREATE `tests/core/agent/test_agent.py`

```python
"""Unit tests for app.core.agent module."""
import os
from unittest.mock import patch

import pytest
from pydantic_ai import Agent


@pytest.mark.unit
def test_vault_agent_is_agent_instance(test_env_vars: dict[str, str]) -> None:
    from app.core.config import get_settings
    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        from app.core.agent.agent import vault_agent
        assert isinstance(vault_agent, Agent)
    get_settings.cache_clear()


@pytest.mark.unit
def test_agent_dependencies_defaults() -> None:
    from app.core.agent.dependencies import AgentDependencies
    deps = AgentDependencies()
    assert deps.request_id == ""


@pytest.mark.unit
def test_agent_dependencies_with_request_id() -> None:
    from app.core.agent.dependencies import AgentDependencies
    deps = AgentDependencies(request_id="test-id")
    assert deps.request_id == "test-id"


@pytest.mark.unit
def test_model_string_format(test_env_vars: dict[str, str]) -> None:
    from app.core.config import get_settings
    get_settings.cache_clear()
    with patch.dict(os.environ, test_env_vars):
        get_settings.cache_clear()
        settings = get_settings()
        assert f"{settings.llm_provider}:{settings.llm_model}" == "anthropic:claude-haiku-4-5-20251001"
    get_settings.cache_clear()
```

- **VALIDATE**: `uv run pytest tests/core/agent/test_agent.py -v -m unit`

---

### TASK 16 — CREATE `tests/features/chat/test_routes.py`

```python
"""Unit tests for app.features.chat.routes."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_chat_requires_auth(app_client: TestClient) -> None:
    response = app_client.post("/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 403


@pytest.mark.unit
def test_chat_rejects_invalid_key(app_client: TestClient) -> None:
    response = app_client.post("/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer wrong-key"})
    assert response.status_code == 401


@pytest.mark.unit
def test_chat_returns_openai_format(app_client: TestClient) -> None:
    mock_result = MagicMock()
    mock_result.output = "Hello from Paddy!"
    mock_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=5)

    with patch("app.features.chat.routes.vault_agent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        response = app_client.post("/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Say hello"}]},
            headers={"Authorization": "Bearer test-bearer-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello from Paddy!"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["id"].startswith("chatcmpl-")


@pytest.mark.unit
def test_extract_user_prompt_returns_last_user_message() -> None:
    from app.features.chat.models import ChatMessage
    from app.shared.openai_adapter import extract_user_prompt
    messages = [ChatMessage(role="user", content="first"),
                ChatMessage(role="assistant", content="resp"),
                ChatMessage(role="user", content="last")]
    assert extract_user_prompt(messages) == "last"


@pytest.mark.unit
def test_extract_user_prompt_raises_on_no_user_message() -> None:
    from app.features.chat.models import ChatMessage
    from app.shared.openai_adapter import extract_user_prompt
    with pytest.raises(ValueError):
        extract_user_prompt([ChatMessage(role="assistant", content="only")])
```

Add missing import at top: `from unittest.mock import patch`

- **VALIDATE**: `uv run pytest tests/features/chat/test_routes.py -v -m unit`

---

## VALIDATION COMMANDS

```bash
# Level 1: Lint + format
uv run ruff check .
uv run ruff format --check .

# Level 2: Type checking
uv run mypy app/
uv run pyright app/

# Level 3: Unit tests
uv run pytest tests/ -v -m unit
uv run pytest app/core/tests/test_config.py -v

# Level 4: Full suite — no regressions
uv run pytest -v -m "not integration"

# Level 5: Manual — start server and test
uv run uvicorn app.main:app --port 8000 --reload
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"messages":[{"role":"user","content":"Say hello and describe what you are."}]}' | jq .
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv add pydantic-ai anthropic python-dotenv` succeeds
- [ ] `Settings` has `llm_provider`, `llm_model`, `llm_api_key`, `api_key` with correct defaults
- [ ] `app/core/agent/` exists with `types.py`, `dependencies.py`, `agent.py`, `__init__.py`
- [ ] `vault_agent` uses `instructions=` (not `system_prompt=`); typed as `Agent[AgentDependencies, str]`
- [ ] `POST /v1/chat/completions` returns 403 without auth, 401 with wrong key, 200 with valid key + mocked LLM
- [ ] `tests/` at project root with all packages and unit tests
- [ ] `ruff check .` → zero errors
- [ ] `mypy app/` → zero errors
- [ ] `pyright app/` → zero errors
- [ ] `pytest -v -m unit` → all pass
- [ ] `pytest -v -m "not integration"` → zero regressions
- [ ] Manual `curl` returns valid OpenAI-format JSON with real LLM response

<!-- EOF -->
