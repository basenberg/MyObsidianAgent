# Feature: Complete Obsidian Copilot Streaming Integration

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Paddy's chat endpoint currently only handles non-streaming (`stream: false`) requests. Obsidian Copilot sends `stream: true` by default for all providers — meaning the integration is broken out of the box. This feature completes the integration by:

1. Implementing SSE (Server-Sent Events) streaming via `agent.iter()` on the existing `POST /v1/chat/completions` endpoint
2. Fixing the `ChatRequest` model to accept `stream: true`, `temperature`, and `max_tokens` fields
3. Fixing the `ChatMessage.content` type to accept `str | list` (required for multimodal messages from Obsidian Copilot)
4. Verifying CORS is correctly configured for Obsidian origins (`app://obsidian.md`, `capacitor://localhost`)
5. Writing a user-facing setup guide in `.agents/reference/obsidian-copilot-setup.md`

All implementation must follow codebase patterns: VSA (features are self-contained slices), structlog keyword-only logging, strict MyPy/Pyright types, and the existing test patterns with `@pytest.mark.unit`.

## User Story

As an Obsidian user
I want to chat with Paddy through the Obsidian Copilot plugin
So that I can query and manage my vault using natural language, with responses streaming in real time

## Problem Statement

Obsidian Copilot sends `"stream": true` by default. Paddy's current endpoint accepts only non-streaming requests (`stream: bool = False`). Additionally, `ChatMessage.content` is typed as `str` only, but Obsidian Copilot sends content as an array when images are attached. CORS origins for Obsidian are already in `.env.example` but need verification.

## Solution Statement

Extend the existing `features/chat/` slice to detect `stream: true` and return a `StreamingResponse` with proper OpenAI SSE chunks generated via `agent.iter()`. The non-streaming path is preserved as a fallback. The system prompt stays in `core/agent/agent.py` (the `instructions=` parameter on `vault_agent`) — the chat route must not define or override it. CORS is already configured via `CORSMiddleware` in `core/middleware.py`; we verify the allowed origins include Obsidian's schemes.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `features/chat/routes.py`, `features/chat/models.py`, `shared/openai_adapter.py`, `core/config.py`, `.agents/reference/`
**Dependencies**: `pydantic-ai>=1.73.0` (already installed), `fastapi` `StreamingResponse` (stdlib)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `app/features/chat/routes.py` — Current endpoint; add streaming branch here. Streaming returns `StreamingResponse | ChatResponse`.
- `app/features/chat/models.py` — `ChatRequest` and `ChatMessage` need field updates.
- `app/shared/openai_adapter.py` — `extract_user_prompt` and `to_pydantic_history` live here; `extract_user_prompt` needs `str | list` handling.
- `app/core/agent/agent.py` — `vault_agent` with `instructions=` system prompt. **Do not replicate the system prompt in routes.**
- `app/core/agent/dependencies.py` — `AgentDependencies` dataclass; already used in routes.
- `app/core/middleware.py` (lines 91–113) — `setup_middleware` adds `CORSMiddleware` reading `settings.allowed_origins`. Verify origins are correct.
- `app/core/config.py` (lines 52–54) — `allowed_origins: list[str]` default and `.env.example` — verify `app://obsidian.md` and `capacitor://localhost` are present.
- `.env.example` — Already has the correct Obsidian origins. Confirm order is correct.
- `tests/features/chat/test_routes.py` — Existing test patterns to mirror for streaming tests.
- `tests/conftest.py` — `app_client` fixture and `test_env_vars` fixture to reuse.
- `tests/core/agent/test_agent.py` — Pattern for patching `vault_agent` in tests.
- `app/core/logging.py` — `get_logger`, `get_request_id` — use these, no custom logging setup.

### New Files to Create

- `tests/features/chat/test_routes_streaming.py` — Unit tests for SSE streaming branch
- `.agents/reference/obsidian-copilot-setup.md` — User-facing setup guide for Obsidian Copilot

### Relevant Research Reports — READ BEFORE IMPLEMENTING

- `.agents/report/research-report-obsidian-copilot-api.md`
  - Section: Endpoint Path Construction — user must set `http://localhost:8000/v1` (not `/v1/chat/completions`)
  - Section: Auth — `Authorization: Bearer <key>`; `"default-key"` sent when no key configured
  - Section: Streaming default — `stream: true` always
  - Section: Request body fields — `model`, `messages`, `stream`, `temperature`, `max_tokens`
- `.agents/report/research-report-pydantic-ai-streaming.md`
  - Section: agent.iter() Mechanics — node types, `ModelRequestNode`, `PartDeltaEvent`, `TextPartDelta.content_delta`
  - Section: FastAPI SSE Implementation — Pattern B (iter-based) with full code blueprint
  - Section: OpenAI Chunk Format — first/middle/final chunk structure and `[DONE]` terminator
  - Section: Message History Conversion — `to_pydantic_history` already implemented correctly

### Patterns to Follow

**VSA Rule:** All changes go inside `features/chat/` (routes and models) or `shared/` (adapter). No new feature directories needed — streaming is part of the existing chat slice.

**Logging Pattern** (from `docs/logging-standard.md`):
```python
logger.info("agent.llm.streaming_started", prompt_length=len(user_prompt))
logger.info("agent.llm.streaming_completed", duration_ms=duration_ms, chunk_count=n)
logger.exception("agent.llm.streaming_failed", fix_suggestion="Retry the request")
```
- Always keyword args only — never f-strings or string formatting in event names
- Use `logger.exception()` in `except` blocks (captures stack trace automatically)
- Include `duration_ms`, `fix_suggestion` on errors

**Type Annotations** (from `docs/mypy-standard.md` and `CLAUDE.md`):
- All parameters and return types must be annotated
- `str | list[Any]` for `ChatMessage.content` — import `Any` from `typing`
- Return type of streaming route: `StreamingResponse | ChatResponse`
- Generator return: `AsyncGenerator[str, None]` or `AsyncIterator[str]`

**Test Pattern** (from `tests/features/chat/test_routes.py`):
```python
@pytest.mark.unit
def test_name(app_client: TestClient) -> None:
    with patch("app.features.chat.routes.vault_agent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        response = app_client.post(...)
    assert response.status_code == 200
```
- Always `@pytest.mark.unit` decorator
- Use `patch()` to mock `vault_agent` — never call real LLM in unit tests
- Fixture `app_client` from `tests/conftest.py` — do not redefine
- For streaming: use `TestClient` with `stream=True` context manager or check response body directly

---

## IMPLEMENTATION PLAN

### Phase 1: Model Updates

Update `ChatMessage` and `ChatRequest` models to accept the full request shape Obsidian Copilot sends. This is a prerequisite for all other work.

**Tasks:**
- Update `ChatMessage.content` to `str | list[Any]`
- Update `ChatRequest.stream` default to `True`, add `temperature` and `max_tokens` fields
- Update `extract_user_prompt` in `openai_adapter.py` to handle `str | list` content

### Phase 2: CORS Verification

Confirm that `app://obsidian.md` and `capacitor://localhost` are in `allowed_origins`. This is already partially in `.env.example` but must be the documented default in `config.py` and verified in tests.

**Tasks:**
- Update `allowed_origins` default in `config.py` to include Obsidian schemes
- Confirm `setup_middleware` applies them correctly (no code change needed, just verification)

### Phase 3: Streaming Implementation

Add the SSE streaming branch to the chat endpoint using `agent.iter()`. The existing non-streaming path remains for `stream: false` fallback.

**Tasks:**
- Implement `_stream_sse` async generator in `routes.py`
- Update `chat_completions` to return `StreamingResponse | ChatResponse` based on `request.stream`
- Use `agent.iter()` (not `run_stream`) per the plan requirement — gives visibility into tool execution for future tool calls

### Phase 4: Testing

Add unit tests for the streaming branch following existing test patterns.

**Tasks:**
- Create `tests/features/chat/test_routes_streaming.py` with streaming-specific tests
- Verify existing non-streaming tests still pass

### Phase 5: User Documentation

Create the Obsidian Copilot setup guide for users.

**Tasks:**
- Write `.agents/reference/obsidian-copilot-setup.md`

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### UPDATE `app/features/chat/models.py`

- **IMPLEMENT**: Change `ChatMessage.content` from `str` to `str | list[Any]`. Add `temperature: float | None = None` and `max_tokens: int | None = None` to `ChatRequest`. Change `stream` default from `False` to `True`.
- **PATTERN**: Existing `ChatRequest`/`ChatMessage` structure in `app/features/chat/models.py`
- **IMPORTS**: Add `from typing import Any` at top of file
- **GOTCHA**: `list[Any]` is used for multimodal content (`[{"type": "text", "text": "..."}]`). Obsidian Copilot uses this when images are attached. MVP does not need to process the array — it only needs to not reject it.
- **GOTCHA**: `stream: bool = True` — the default flips to `True` to match Obsidian Copilot's behavior. The non-streaming fallback path is still preserved.
- **VALIDATE**: `uv run ruff check app/features/chat/models.py && uv run mypy app/features/chat/models.py`

The updated `ChatRequest` model:

```python
class ChatRequest(BaseModel):
    model: str = "paddy"
    messages: list[ChatMessage]
    stream: bool = True          # Changed from False — Copilot default is True
    temperature: float | None = None
    max_tokens: int | None = None
```

The updated `ChatMessage` model:

```python
from typing import Any

class ChatMessage(BaseModel):
    role: str
    content: str | list[Any]    # list[Any] for multimodal (image) messages
```

---

### UPDATE `app/shared/openai_adapter.py` — `extract_user_prompt`

- **IMPLEMENT**: Update `extract_user_prompt` to handle `content` being a `str | list[Any]`. When content is a list, extract the text from the first `{"type": "text", "text": "..."}` element. If no text element found, return empty string (do not raise).
- **PATTERN**: Mirror `extractDeltaContent` from Obsidian Copilot source (see `.agents/report/research-report-obsidian-copilot-api.md` Section 8)
- **IMPORTS**: `from typing import Any`; update `ChatMessage` import — already imported
- **GOTCHA**: `to_pydantic_history` passes `msg.content` directly to `UserPromptPart(content=...)`. Pydantic AI accepts `str | Sequence[UserContent]` for `content` — plain strings work. For list content, extract the text string to stay compatible.
- **VALIDATE**: `uv run ruff check app/shared/openai_adapter.py && uv run mypy app/shared/openai_adapter.py`

Updated `extract_user_prompt`:

```python
def extract_user_prompt(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            if isinstance(msg.content, str):
                return msg.content
            # Multimodal: extract first text part
            for part in msg.content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    return text if isinstance(text, str) else ""
            return ""
    raise ValueError("No user message found in messages list.")
```

---

### UPDATE `app/core/config.py` — CORS defaults

- **IMPLEMENT**: Update `allowed_origins` default to include `app://obsidian.md` and `capacitor://localhost`. The current default only has `http://localhost:3000` and `http://localhost:8123`.
- **PATTERN**: Existing `allowed_origins: list[str]` field in `Settings` class
- **GOTCHA**: Do NOT change `setup_middleware` in `core/middleware.py` — it already reads `settings.allowed_origins` correctly. Only the default value in `config.py` needs updating.
- **GOTCHA**: `.env.example` already has the correct value. This task ensures the in-code default matches so Docker deployments without a `.env` file work correctly.
- **VALIDATE**: `uv run mypy app/core/config.py`

Updated default:

```python
allowed_origins: list[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8123",
    "app://obsidian.md",
    "capacitor://localhost",
]
```

---

### UPDATE `app/features/chat/routes.py` — Add streaming branch

- **IMPLEMENT**:
  1. Add `_stream_sse` async generator function that uses `agent.iter()`
  2. Update `chat_completions` return type to `StreamingResponse | ChatResponse`
  3. Branch on `request.stream`: if `True` return `StreamingResponse(_stream_sse(...))`, else use existing `vault_agent.run(...)` path
- **PATTERN**: `agent.iter()` node iteration from `.agents/report/research-report-pydantic-ai-streaming.md` — Pattern B (iter-based)
- **PATTERN**: Logging pattern from `app/features/chat/routes.py` lines 59–82 — use same `agent.llm.*` events
- **IMPORTS**: Add `import json`, `import uuid`, `from collections.abc import AsyncIterator`, `from fastapi.responses import StreamingResponse`, `from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta`
- **GOTCHA**: `agent.iter()` requires `async with` context manager. The generator must `yield` inside the `async with` block. This works correctly in an `async def` generator.
- **GOTCHA**: Do NOT pass a `system_prompt` or `instructions` parameter to `agent.iter()`. The system prompt is defined in `core/agent/agent.py` as the `instructions=` argument on `vault_agent`. The chat route must not override it.
- **GOTCHA**: FastAPI `StreamingResponse` requires `media_type="text/event-stream"`. Add `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers to prevent proxy buffering.
- **GOTCHA**: SSE format is `f"data: {json.dumps(payload)}\n\n"` — exactly two newlines. `data: [DONE]\n\n` terminates the stream.
- **GOTCHA**: The `chunk_id` must be the SAME value for all chunks in one response. Generate it once before the loop.
- **VALIDATE**: `uv run ruff check app/features/chat/routes.py && uv run mypy app/features/chat/routes.py`

The `_stream_sse` function signature and structure:

```python
async def _stream_sse(
    user_prompt: str,
    history: list[ModelMessage],
    deps: AgentDependencies,
    model_name: str,
) -> AsyncIterator[str]:
    """Async generator yielding OpenAI SSE chunks from vault_agent.iter().

    Args:
        user_prompt: The current user message text.
        history: Prior conversation turns as Pydantic AI ModelMessage list.
        deps: Agent dependencies (request_id for correlation).
        model_name: Model name string to echo back in response chunks.

    Yields:
        SSE-formatted strings: "data: {json}\\n\\n", ending with "data: [DONE]\\n\\n".
    """
```

The updated route signature:

```python
@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
) -> StreamingResponse | ChatResponse:
```

Note: `response_model=None` is required when returning `StreamingResponse` — FastAPI cannot serialize it through a Pydantic model.

The streaming chunk helper inside `_stream_sse`:

```python
def _make_chunk(chunk_id: str, created: int, model_name: str, delta: dict[str, Any], finish_reason: str | None = None) -> str:
    payload: dict[str, Any] = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_name,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n"
```

The full `_stream_sse` iteration logic:

```python
import time as _time

chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
created = int(_time.time())
chunk_count = 0
start = _time.time()

logger.info("agent.llm.streaming_started", prompt_length=len(user_prompt))

# First chunk: role announcement
yield _make_chunk(chunk_id, created, model_name, {"role": "assistant", "content": ""})

try:
    async with vault_agent.iter(user_prompt, deps=deps, message_history=history) as run:
        async for node in run:
            if vault_agent.is_model_request_node(node):
                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        if isinstance(event, PartStartEvent):
                            if hasattr(event.part, "content") and event.part.content:
                                yield _make_chunk(chunk_id, created, model_name, {"content": event.part.content})
                                chunk_count += 1
                        elif isinstance(event, PartDeltaEvent):
                            if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                                yield _make_chunk(chunk_id, created, model_name, {"content": event.delta.content_delta})
                                chunk_count += 1
except Exception:
    logger.exception(
        "agent.llm.streaming_failed",
        fix_suggestion="Check LLM_API_KEY and LLM_PROVIDER config, then retry",
    )
    yield _make_chunk(chunk_id, created, model_name, {"content": "\n\n[Error: agent failed to respond]"})

duration_ms = round((_time.time() - start) * 1000, 2)
logger.info("agent.llm.streaming_completed", duration_ms=duration_ms, chunk_count=chunk_count)

# Final stop chunk
yield _make_chunk(chunk_id, created, model_name, {}, finish_reason="stop")
yield "data: [DONE]\n\n"
```

The `chat_completions` branching logic:

```python
user_prompt = extract_user_prompt(request.messages)
history = to_pydantic_history(request.messages)
deps = AgentDependencies(request_id=get_request_id())

if request.stream:
    return StreamingResponse(
        _stream_sse(user_prompt, history, deps, request.model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# Non-streaming fallback (existing path)
start = time.time()
logger.info("agent.llm.call_started", prompt_length=len(user_prompt))
result = await vault_agent.run(user_prompt, deps=deps, message_history=history)
usage = result.usage()
duration_ms = round((time.time() - start) * 1000, 2)
logger.info(
    "agent.llm.call_completed",
    duration_ms=duration_ms,
    tokens_prompt=usage.input_tokens,
    tokens_completion=usage.output_tokens,
)
return to_openai_response(result.output, usage.input_tokens, usage.output_tokens)
```

---

### CREATE `tests/features/chat/test_routes_streaming.py`

- **IMPLEMENT**: Unit tests for the SSE streaming branch. Tests must mock `vault_agent.iter` so no real LLM is called. Use `app_client` fixture from `tests/conftest.py`.
- **PATTERN**: Mirror `tests/features/chat/test_routes.py` — `@pytest.mark.unit`, `patch()`, `app_client` fixture
- **IMPORTS**: `from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock`
- **GOTCHA**: `agent.iter()` is an `@asynccontextmanager`. To mock it, you need `MagicMock` with `__aenter__` and `__aexit__` returning async mocks. The iterator must yield node mocks that respond correctly to `vault_agent.is_model_request_node()`.
- **GOTCHA**: The simplest test approach is to send `stream=True` and check that the response is `text/event-stream` content type, contains `data:` lines, and ends with `data: [DONE]`. Verifying exact chunk content is secondary to verifying the format.
- **GOTCHA**: `TestClient` from Starlette supports streaming responses — use `with app_client.stream("POST", ...) as response:` and collect lines.
- **VALIDATE**: `uv run pytest tests/features/chat/test_routes_streaming.py -v -m unit`

Tests to implement:

1. `test_streaming_returns_event_stream_content_type` — verify `Content-Type: text/event-stream`
2. `test_streaming_response_contains_done_terminator` — verify `data: [DONE]` present in body
3. `test_streaming_chunks_have_required_fields` — verify `id`, `object`, `choices[0].delta` present in at least one parsed chunk
4. `test_streaming_requires_auth` — verify 403 without Authorization header (same as non-streaming)
5. `test_non_streaming_still_works_when_stream_false` — verify existing behavior preserved with `stream=False`

For mocking `agent.iter()`, use a simpler approach: patch `vault_agent.iter` with a context manager that yields no nodes (empty run). This results in just the role announcement chunk + `[DONE]`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def mock_iter(*args, **kwargs):
    mock_run = MagicMock()
    mock_run.__aiter__ = MagicMock(return_value=iter([]))  # no nodes
    yield mock_run

with patch("app.features.chat.routes.vault_agent.iter", new=mock_iter):
    with app_client.stream("POST", "/v1/chat/completions", json=..., headers=...) as response:
        body = response.read().decode()
```

---

### CREATE `.agents/reference/obsidian-copilot-setup.md`

- **IMPLEMENT**: User-facing setup guide covering: prerequisites, plugin installation, Paddy configuration in Obsidian Copilot (base URL, API key, model name), Docker startup, and troubleshooting.
- **CONTENT REQUIREMENTS** (based on research in `.agents/report/research-report-obsidian-copilot-api.md`):
  - Base URL must be `http://localhost:8000/v1` — NOT `http://localhost:8000` (the OpenAI SDK appends `/chat/completions`)
  - API key field in Copilot: set to match `API_KEY` in `.env`; if left blank, `"default-key"` is sent
  - Provider type in Copilot: select **"3rd party (openai-format)"**
  - Model name: any string (e.g. `paddy`) — Paddy ignores this and uses its configured LLM
  - CORS: Obsidian uses `app://obsidian.md` and `capacitor://localhost` as origins — these are in Paddy's `ALLOWED_ORIGINS` by default
  - Streaming: enabled by default in Copilot — Paddy supports this natively
  - Troubleshooting: common issues (wrong base URL, missing API key, CORS errors)

---

## TESTING STRATEGY

### Unit Tests

All tests use `@pytest.mark.unit` and must not require a real LLM or network connection. Mock `vault_agent.iter` and `vault_agent.run` at the route level.

**Existing tests to verify still pass:**
- `tests/features/chat/test_routes.py` — non-streaming path; `stream=False` must still work
- `tests/core/agent/test_agent.py` — agent instantiation tests

**New tests in `tests/features/chat/test_routes_streaming.py`:**
- Content-Type is `text/event-stream` when `stream=True`
- Response body contains `data: [DONE]` terminator
- At least one chunk has required OpenAI fields (`id`, `object`, `choices`)
- Auth is still enforced on streaming endpoint (403 without header)
- `stream=False` fallback path still returns non-streaming `chat.completion` object

### Integration Tests

Not required for this feature. The streaming path calls the LLM exactly as the non-streaming path does — integration is covered by the existing agent tests.

### Edge Cases

- `messages` array with only a system message and no user message → `ValueError` from `extract_user_prompt` → handled by global exception handler → 500 response
- `content` as empty list → `extract_user_prompt` returns `""` → agent receives empty prompt
- `stream=True` request where agent raises mid-stream → error chunk yielded before `[DONE]`, stream terminates cleanly
- `stream=True` with no messages → Pydantic validation error → 422 before handler is called

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check app/features/chat/ app/shared/openai_adapter.py app/core/config.py
uv run ruff format --check app/features/chat/ app/shared/openai_adapter.py app/core/config.py
```

### Level 2: Type Checking

```bash
uv run mypy app/features/chat/ app/shared/openai_adapter.py app/core/config.py
uv run pyright app/
```

### Level 3: Unit Tests

```bash
# Run only new streaming tests
uv run pytest tests/features/chat/test_routes_streaming.py -v -m unit

# Run full chat feature test suite (must not regress)
uv run pytest tests/features/chat/ -v -m unit

# Run full test suite
uv run pytest -v -m unit
```

### Level 4: Manual Validation

```bash
# Start Paddy locally
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Test non-streaming (stream=false)
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello Paddy"}],"stream":false}' | jq .

# Test SSE streaming (stream=true — the default)
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello in one sentence"}],"stream":true}'
# Expected: SSE lines starting with "data: {", ending with "data: [DONE]"

# Verify CORS preflight for Obsidian origin
curl -s -X OPTIONS http://localhost:8000/v1/chat/completions \
  -H "Origin: app://obsidian.md" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization,Content-Type" \
  -v 2>&1 | grep -i "access-control"
# Expected: Access-Control-Allow-Origin: app://obsidian.md
```

### Level 5: Obsidian Copilot Plugin Validation

Once the above passes:

1. Start Paddy via `docker compose up` (or local uvicorn)
2. Open Obsidian → Settings → Obsidian Copilot
3. Set **Model**: any custom model entry with provider `3rd party (openai-format)`
4. Set **Base URL**: `http://localhost:8000/v1`
5. Set **API Key**: value matching `API_KEY` in `.env`
6. Set **Model Name**: `paddy`
7. Open Copilot chat, type a message, verify streaming response appears

---

## ACCEPTANCE CRITERIA

- [ ] `POST /v1/chat/completions` returns `text/event-stream` response when `stream: true`
- [ ] Streaming response body contains valid OpenAI SSE chunks with `choices[0].delta.content`
- [ ] Streaming response terminates with `data: [DONE]`
- [ ] `stream: false` path continues to return standard `chat.completion` JSON object
- [ ] `ChatMessage.content` accepts both `str` and `list` without validation error
- [ ] `ChatRequest` accepts `temperature` and `max_tokens` fields without error
- [ ] CORS headers include `app://obsidian.md` and `capacitor://localhost` in `allowed_origins`
- [ ] System prompt is NOT redefined in `routes.py` — it remains in `core/agent/agent.py` only
- [ ] All new and existing unit tests pass with `uv run pytest -v -m unit`
- [ ] `uv run mypy app/` exits with zero errors
- [ ] `uv run pyright app/` exits with zero errors
- [ ] `uv run ruff check .` exits with zero errors
- [ ] `.agents/reference/obsidian-copilot-setup.md` exists with correct base URL instruction (`/v1` suffix)
- [ ] Manual `curl` SSE test produces valid streaming chunks

---

## COMPLETION CHECKLIST

- [ ] `app/features/chat/models.py` updated — `content: str | list[Any]`, `stream: bool = True`, `temperature` and `max_tokens` fields added
- [ ] `app/shared/openai_adapter.py` updated — `extract_user_prompt` handles `str | list`
- [ ] `app/core/config.py` updated — `allowed_origins` default includes Obsidian origins
- [ ] `app/features/chat/routes.py` updated — streaming branch with `_stream_sse` generator, `response_model=None`, correct return type annotation
- [ ] `tests/features/chat/test_routes_streaming.py` created — 5 unit tests passing
- [ ] `.agents/reference/obsidian-copilot-setup.md` created — user setup guide
- [ ] All validation commands executed, all green
- [ ] Manual SSE curl test verified
- [ ] Obsidian Copilot plugin test (Level 5) completed

---

## NOTES

### Why `agent.iter()` instead of `run_stream()`?

The plan specifies `agent.iter()` explicitly. While `run_stream()` is simpler for basic text streaming, `agent.iter()` gives per-node visibility: when vault tools are implemented (`obsidian_query_vault`, etc.), tool call events can be surfaced to the client (e.g., showing "Searching vault..." as a status update in the stream). Starting with `agent.iter()` avoids a future refactor.

### System Prompt Location

The `vault_agent` in `core/agent/agent.py` is defined with `instructions="You are Paddy..."`. This is the agent's system prompt. Pydantic AI injects it automatically on every `agent.iter()` / `agent.run()` call. The chat route **must not** pass `instructions=` or any system prompt override — doing so would duplicate or conflict with the agent's configured behavior.

### CORS Origins

Obsidian desktop uses the `app://obsidian.md` origin. Obsidian mobile (via Capacitor) uses `capacitor://localhost`. Both are non-HTTP schemes that must be explicitly listed — wildcard `*` does not cover them in all browser/Electron contexts.

### `response_model=None` on the route

When a FastAPI route returns `StreamingResponse`, the `response_model` parameter must be `None` (or omitted with `response_model=None`). If left as `response_model=ChatResponse`, FastAPI will attempt to serialize the streaming response through the Pydantic model and fail.

### `data:` line format

Every SSE event line is `data: {json}\n\n` — exactly two `\n` characters at the end. The `[DONE]` terminator is `data: [DONE]\n\n` — it is NOT valid JSON and must not be passed through `json.dumps`.

<!-- EOF -->
