"""POST /v1/chat/completions — OpenAI-compatible chat endpoint."""

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from app.core.agent.agent import vault_agent
from app.core.agent.dependencies import AgentDependencies
from app.core.config import get_settings
from app.core.logging import get_logger, get_request_id
from app.features.chat.models import ChatRequest, ChatResponse
from app.shared.openai_adapter import extract_user_prompt, to_openai_response, to_pydantic_history

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate Bearer token against the configured API_KEY setting.

    Args:
        credentials: HTTPBearer credentials extracted from Authorization header.

    Returns:
        The validated API key token.

    Raises:
        HTTPException: 401 if the token does not match the configured API key.
    """
    if credentials.credentials != get_settings().api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return credentials.credentials


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
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    chunk_count = 0
    start = time.time()

    def _make_chunk(delta: dict[str, Any], finish_reason: str | None = None) -> str:
        payload: dict[str, Any] = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    logger.info("agent.llm.streaming_started", prompt_length=len(user_prompt))

    # First chunk: role announcement
    yield _make_chunk({"role": "assistant", "content": ""})

    try:
        async with vault_agent.iter(user_prompt, deps=deps, message_history=history) as run:
            async for node in run:
                if vault_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent):
                                if isinstance(event.part, TextPart) and event.part.content:
                                    yield _make_chunk({"content": event.part.content})
                                    chunk_count += 1
                            elif isinstance(event, PartDeltaEvent):
                                if (
                                    isinstance(event.delta, TextPartDelta)
                                    and event.delta.content_delta
                                ):
                                    yield _make_chunk({"content": event.delta.content_delta})
                                    chunk_count += 1
    except Exception:
        logger.exception(
            "agent.llm.streaming_failed",
            fix_suggestion="Check LLM_API_KEY and LLM_PROVIDER config, then retry",
        )
        yield _make_chunk({"content": "\n\n[Error: agent failed to respond]"})

    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info("agent.llm.streaming_completed", duration_ms=duration_ms, chunk_count=chunk_count)

    # Final stop chunk + stream terminator
    yield _make_chunk({}, finish_reason="stop")
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
) -> StreamingResponse | ChatResponse:
    """Handle OpenAI-compatible chat completion requests.

    Accepts the full Obsidian Copilot message history, runs the vault_agent,
    and returns either a streaming SSE response or an OpenAI-format JSON response.

    Args:
        request: OpenAI-format chat completion request.
        _api_key: Validated API key — injected by verify_api_key dependency.

    Returns:
        StreamingResponse (text/event-stream) when stream=True, or
        ChatResponse (JSON) when stream=False.
    """
    logger.info(
        "request.chat_received",
        message_count=len(request.messages),
        model=request.model,
        stream=request.stream,
    )

    user_prompt = extract_user_prompt(request.messages)
    history = to_pydantic_history(request.messages)
    deps = AgentDependencies(
        request_id=get_request_id(),
        vault_path=get_settings().vault_path,
    )

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


@router.post("/v1/embeddings", response_model=None)
async def embeddings_stub() -> dict[str, Any]:
    """Stub embeddings endpoint — returns empty list.

    Obsidian Copilot probes this endpoint to detect embedding support.
    Paddy does not implement embeddings; returning an empty valid response
    prevents 404 log noise without advertising false capability.

    Returns:
        OpenAI-compatible empty embeddings list response.
    """
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": [0.0]}],
        "model": "paddy",
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
