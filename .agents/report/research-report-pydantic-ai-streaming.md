# Pydantic AI Streaming + OpenAI SSE — Implementation Reference

**Sources:** Pydantic AI docs/source, pydantic/pydantic-ai GitHub, logancyang/obsidian-copilot source, OpenAI streaming spec
**Date:** 2026-03-28

---

## Part 1 — agent.iter() Mechanics

### Full Signature

```python
@asynccontextmanager
async def iter(
    self,
    user_prompt: str | Sequence[_messages.UserContent] | None = None,
    *,
    output_type: OutputSpec[Any] | None = None,
    message_history: Sequence[_messages.ModelMessage] | None = None,
    deferred_tool_results: DeferredToolResults | None = None,
    model: models.Model | models.KnownModelName | str | None = None,
    instructions: AgentInstructions[AgentDepsT] = None,
    deps: AgentDepsT = None,
    model_settings: AgentModelSettings[AgentDepsT] | None = None,
    usage_limits: _usage.UsageLimits | None = None,
    usage: _usage.RunUsage | None = None,
    metadata: AgentMetadata[AgentDepsT] | None = None,
    infer_name: bool = True,
    toolsets: Sequence[AbstractToolset[AgentDepsT]] | None = None,
    builtin_tools: Sequence[AgentBuiltinTool[AgentDepsT]] | None = None,
    spec: dict[str, Any] | AgentSpec | None = None,
) -> AsyncIterator[AgentRun[AgentDepsT, Any]]
```

### What `async with agent.iter(...)` Gives You

`agent.iter()` is an `@asynccontextmanager` that yields an `AgentRun[AgentDepsT, OutputDataT]`:

```python
async with agent.iter('What is the capital of France?') as agent_run:
    # agent_run is AgentRun[AgentDepsT, OutputDataT]
    async for node in agent_run:
        nodes.append(node)
    print(agent_run.result.output)
```

### AgentRun Class

```python
class AgentRun:
    ctx: RunContext[AgentDepsT]          # current execution context
    next_node: AgentRunNode              # upcoming node to execute
    result: AgentRunResult | None        # None until run completes

    async def __aiter__() -> AsyncIterator[AgentRunNode]
    async def __anext__() -> AgentRunNode
    async def next(node) -> AgentRunNode | None  # manual advance

    def all_messages() -> list[ModelMessage]
    def new_messages() -> list[ModelMessage]
    def all_messages_json() -> bytes
    def new_messages_json() -> bytes

    @property def usage() -> RunUsage
    @property def run_id() -> str
```

### Node Types Yielded by `async for node in agent_run`

From `_agent_graph.py`:

| Node class | What it represents |
|---|---|
| `UserPromptNode` | Handles user prompt + system prompts; yields first |
| `ModelRequestNode` | Makes LLM request — **stream tokens here** |
| `CallToolsNode` | Processes model response; decides end or new request |
| `SetFinalResult` | Ends after streaming response produced final result |
| `End` (from `pydantic_graph`) | Terminal sentinel; signals run is complete |

### Detecting Node Types and Streaming

```python
from pydantic_ai import Agent
from pydantic_graph import End

async with agent.iter(user_prompt) as run:
    async for node in run:
        if Agent.is_user_prompt_node(node):
            pass
        elif Agent.is_model_request_node(node):
            # Stream tokens from the LLM
            async with node.stream(run.ctx) as request_stream:
                async for event in request_stream:
                    pass
        elif Agent.is_call_tools_node(node):
            # Tool execution
            async with node.stream(run.ctx) as tool_stream:
                async for event in tool_stream:
                    pass
        elif Agent.is_end_node(node):
            print(run.result.output)
```

### Stream Event Types

```python
# ModelResponseStreamEvent — from ModelRequestNode.stream()
ModelResponseStreamEvent: TypeAlias = PartStartEvent | PartDeltaEvent | PartEndEvent

# AgentStreamEvent — full union including tool events
AgentStreamEvent: TypeAlias = (
    PartStartEvent | PartDeltaEvent | PartEndEvent
    | FinalResultEvent
    | FunctionToolCallEvent | FunctionToolResultEvent
    | BuiltinToolCallEvent | BuiltinToolResultEvent
    | HandleResponseEvent
)
```

Key event dataclasses:

```python
@dataclass
class PartStartEvent:
    index: int
    part: ModelResponsePart          # TextPart | ToolCallPart | ...
    previous_part_kind: str | None
    event_kind: Literal['part-start']

@dataclass
class PartDeltaEvent:
    index: int
    delta: ModelResponsePartDelta    # TextPartDelta | ToolCallPartDelta
    event_kind: Literal['part-delta']

@dataclass
class TextPartDelta:
    content_delta: str               # ← THE TEXT CHUNK TO STREAM
    part_delta_kind: Literal['text-delta']

@dataclass
class FunctionToolCallEvent:
    part: ToolCallPart
    event_kind: Literal['function-tool-call']

@dataclass
class FunctionToolResultEvent:
    result: ToolReturn
    event_kind: Literal['function-tool-result']
```

### Extracting Text Content from ModelRequestNode

```python
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

async with node.stream(run.ctx) as request_stream:
    async for event in request_stream:
        if isinstance(event, PartStartEvent):
            # Initial content (if any) when the part begins
            if hasattr(event.part, 'content') and event.part.content:
                yield event.part.content
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                yield event.delta.content_delta   # ← the actual text increment
```

### Getting Final Output

```python
async with agent.iter('prompt', message_history=history) as run:
    async for node in run:
        pass  # exhaust all nodes
    # After loop:
    output = run.result.output
```

---

## Part 2 — agent.run_stream() — Simpler Alternative

### Full Signature

```python
@asynccontextmanager
async def run_stream(
    self,
    user_prompt: str | Sequence[UserContent] | None = None,
    *,
    output_type: OutputSpec[Any] | None = None,
    message_history: Sequence[ModelMessage] | None = None,
    model: Model | KnownModelName | str | None = None,
    deps: AgentDepsT = None,
    model_settings: ModelSettings | None = None,
    usage_limits: UsageLimits | None = None,
    usage: RunUsage | None = None,
    infer_name: bool = True,
) -> AbstractAsyncContextManager[StreamedRunResult[AgentDepsT, OutputDataT]]
```

### `stream_text(delta=True)` — The Key SSE Method

```python
async def stream_text(
    self,
    *,
    delta: bool = False,
    # delta=True: yield only NEW increment each time (use for SSE)
    # delta=False: yield full accumulated text (default, not useful for SSE)
    debounce_by: float | None = 0.1,
    # debounce_by=None: no batching, lowest latency
    # debounce_by=0.1: group chunks within 100ms window
) -> AsyncIterator[str]: ...
```

**Note:** Result validators are skipped when `delta=True`.

### StreamedRunResult Methods

```python
async def stream_text(*, delta: bool = False, debounce_by: float | None = 0.1) -> AsyncIterator[str]
async def stream_output(*, debounce_by: float | None = 0.1) -> AsyncIterator[OutputDataT]
async def get_output() -> OutputDataT          # consume entire stream
def new_messages(...) -> list[ModelMessage]
def new_messages_json(...) -> bytes
def usage() -> RunUsage                        # incomplete until stream finishes
@property is_complete: bool
@property run_id: str
```

### run_stream vs iter() Comparison

| | `run_stream()` | `agent.iter()` |
|---|---|---|
| Simplicity | Much simpler | More complex |
| Tool call visibility | Hidden (transparent) | Full per-node visibility |
| Text streaming | `stream_text(delta=True)` | `PartDeltaEvent.delta.content_delta` |
| Use case | Basic SSE chat | Custom streaming, tool progress events |

**Decision:** For Paddy's `/v1/chat/completions` endpoint, use `run_stream()`. Use `iter()` only if emitting tool-call progress events to the client.

---

## Part 3 — Message History Conversion

### Pydantic AI Message Types

```python
ModelMessage = Annotated[ModelRequest | ModelResponse, pydantic.Discriminator('kind')]

@dataclass
class ModelRequest:
    parts: Sequence[ModelRequestPart]   # SystemPromptPart | UserPromptPart | ToolReturnPart
    kind: Literal['request'] = 'request'

@dataclass
class ModelResponse:
    parts: Sequence[ModelResponsePart]  # TextPart | ToolCallPart
    kind: Literal['response'] = 'response'

@dataclass
class UserPromptPart:
    content: str | Sequence[UserContent]
    part_kind: Literal['user-prompt'] = 'user-prompt'

@dataclass
class TextPart:
    content: str
    part_kind: Literal['text'] = 'text'

@dataclass
class SystemPromptPart:
    content: str
    part_kind: Literal['system-prompt'] = 'system-prompt'

@dataclass
class ToolCallPart:
    tool_name: str
    args: str | dict[str, Any] | None = None
    tool_call_id: str = field(default_factory=_generate_tool_call_id)
    part_kind: Literal['tool-call'] = 'tool-call'

@dataclass
class ToolReturnPart:
    tool_name: str
    content: ToolReturnContent
    tool_call_id: str
    outcome: Literal['success', 'failed', 'denied'] = 'success'
    part_kind: Literal['tool-return'] = 'tool-return'
```

### OpenAI → Pydantic AI Conversion Function

There is **no built-in conversion utility** in Pydantic AI. Must be written manually:

```python
from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from app.features.chat.models import ChatMessage


def to_pydantic_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert OpenAI-format messages to Pydantic AI ModelMessage history.

    Excludes the last user message — that becomes the user_prompt arg to
    agent.run() or agent.run_stream(). Skips system messages (the agent
    handles system prompt via its instructions parameter).

    Args:
        messages: Full conversation history from the OpenAI request.

    Returns:
        List of Pydantic AI ModelMessage objects representing prior turns.
    """
    history: list[ModelMessage] = []
    # Exclude the last user message — it becomes the user_prompt argument
    msgs = messages[:-1] if messages and messages[-1].role == "user" else messages
    for msg in msgs:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        elif msg.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
        # system messages: skipped — agent handles via instructions
    return history


def extract_user_prompt(messages: list[ChatMessage]) -> str:
    """Return content of the last user message.

    Args:
        messages: Full conversation history from the OpenAI request.

    Returns:
        Content string of the last user message.

    Raises:
        ValueError: If no user message exists in messages.
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    raise ValueError("No user message found in messages list.")
```

### Serialization for Persistence

```python
from pydantic_ai import ModelMessagesTypeAdapter

# Serialize to JSON bytes
json_bytes: bytes = ModelMessagesTypeAdapter.dump_json(messages)

# Deserialize from JSON bytes
messages: list[ModelMessage] = ModelMessagesTypeAdapter.validate_json(json_bytes)
```

---

## Part 4 — FastAPI SSE Implementation Blueprint

### Pattern A: `run_stream()` — Recommended for Paddy

```python
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.config import get_settings
from app.core.logging import get_logger, get_request_id
from app.features.chat.models import ChatRequest, ChatResponse
from app.shared.openai_adapter import extract_user_prompt, to_openai_response, to_pydantic_history

router = APIRouter()
logger = get_logger(__name__)
security = HTTPBearer()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
) -> StreamingResponse | ChatResponse:
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
    else:
        # Non-streaming fallback
        result = await vault_agent.run(user_prompt, deps=deps, message_history=history)
        usage = result.usage()
        return to_openai_response(result.output, usage.input_tokens, usage.output_tokens)


async def _stream_sse(
    user_prompt: str,
    history: list,
    deps: AgentDependencies,
    model_name: str,
) -> AsyncIterator[str]:
    """Async generator yielding OpenAI SSE chunks."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def make_chunk(delta: dict, finish_reason: str | None = None) -> str:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    # First chunk: role announcement
    yield make_chunk({"role": "assistant", "content": ""})

    try:
        async with vault_agent.run_stream(
            user_prompt, deps=deps, message_history=history
        ) as result:
            async for delta_text in result.stream_text(delta=True, debounce_by=None):
                if delta_text:
                    yield make_chunk({"content": delta_text})
    except Exception:
        logger.exception("agent.stream.failed")
        yield make_chunk({"content": "\n\n[Error: agent failed]"})

    # Final chunk
    yield make_chunk({}, finish_reason="stop")
    yield "data: [DONE]\n\n"
```

### Pattern B: `agent.iter()` — When Tool Events Are Needed

```python
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

async def _stream_sse_with_iter(
    user_prompt: str,
    history: list,
    deps: AgentDependencies,
    model_name: str,
) -> AsyncIterator[str]:
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def make_chunk(delta: dict, finish_reason: str | None = None) -> str:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield make_chunk({"role": "assistant", "content": ""})

    try:
        async with vault_agent.iter(user_prompt, deps=deps, message_history=history) as run:
            async for node in run:
                if vault_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent):
                                if hasattr(event.part, "content") and event.part.content:
                                    yield make_chunk({"content": event.part.content})
                            elif isinstance(event, PartDeltaEvent):
                                if (
                                    isinstance(event.delta, TextPartDelta)
                                    and event.delta.content_delta
                                ):
                                    yield make_chunk({"content": event.delta.content_delta})
    except Exception:
        logger.exception("agent.stream.failed")
        yield make_chunk({"content": "\n\n[Error: agent failed]"})

    yield make_chunk({}, finish_reason="stop")
    yield "data: [DONE]\n\n"
```

---

## Part 5 — OpenAI Streaming Chunk Format (Exact Spec)

### First Chunk (Role Announcement)

```json
{
  "id": "chatcmpl-9lMgfRSWPHcw51s6wxKT1YEO2CKpd",
  "object": "chat.completion.chunk",
  "created": 1721075653,
  "model": "paddy",
  "choices": [
    {
      "index": 0,
      "delta": { "role": "assistant", "content": "" },
      "finish_reason": null
    }
  ]
}
```

### Content Delta Chunks

```json
{
  "id": "chatcmpl-9lMgfRSWPHcw51s6wxKT1YEO2CKpd",
  "object": "chat.completion.chunk",
  "created": 1721075653,
  "model": "paddy",
  "choices": [
    {
      "index": 0,
      "delta": { "content": "Hello" },
      "finish_reason": null
    }
  ]
}
```

### Final Chunk (Stop)

```json
{
  "id": "chatcmpl-9lMgfRSWPHcw51s6wxKT1YEO2CKpd",
  "object": "chat.completion.chunk",
  "created": 1721075653,
  "model": "paddy",
  "choices": [
    {
      "index": 0,
      "delta": {},
      "finish_reason": "stop"
    }
  ]
}
```

### Terminator

```
data: [DONE]

```

(Exactly `data: [DONE]` followed by two newlines.)

### Field Requirements

| Field | Required | Notes |
|---|---|---|
| `id` | Yes | Same value for all chunks in one response |
| `object` | Yes | Always `"chat.completion.chunk"` |
| `created` | Yes | Unix timestamp, same for all chunks |
| `model` | Yes | Model name string |
| `choices` | Yes | Array with 1 element |
| `choices[].index` | Yes | Always `0` |
| `choices[].delta` | Yes | `{"role","content"}` first; `{"content"}` middle; `{}` final |
| `choices[].finish_reason` | Yes | `null` for all except final; `"stop"` on final |
| `usage` | No | Only if `stream_options.include_usage=true` in request |

---

## Part 6 — Complete Flow

```
POST /v1/chat/completions
  → ChatRequest (messages, stream=True)
  → extract_user_prompt(messages)        # last user message content
  → to_pydantic_history(messages)        # all prior messages as ModelMessage list
  → AgentDependencies(request_id=...)
  → StreamingResponse(_stream_sse(...))
      → yield first chunk (role: assistant)
      → async with vault_agent.run_stream(user_prompt, message_history=history) as result:
          → async for delta in result.stream_text(delta=True, debounce_by=None):
              → yield SSE chunk: {"delta": {"content": delta}}
      → yield final chunk: {"delta": {}, "finish_reason": "stop"}
      → yield "data: [DONE]\n\n"
```

---

## Summary — Key Implementation Decisions

| Decision | Choice | Reason |
|---|---|---|
| Streaming API | `run_stream()` | Simpler; handles tool calls internally |
| Delta streaming | `stream_text(delta=True)` | Only new text per chunk |
| Debouncing | `debounce_by=None` | Lowest latency for SSE |
| SSE media type | `text/event-stream` | Required by spec |
| Chunk format | `data: {json}\n\n` | Standard SSE format |
| History conversion | Manual (no built-in) | Convert `user→ModelRequest`, `assistant→ModelResponse` |
| stream=False fallback | `agent.run()` | Existing implementation, keep it |
