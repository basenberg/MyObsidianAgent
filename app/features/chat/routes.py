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


@router.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
) -> ChatResponse:
    """Handle OpenAI-compatible chat completion requests.

    Accepts the full Obsidian Copilot message history, runs the vault_agent,
    and returns an OpenAI-format response.

    Args:
        request: OpenAI-format chat completion request.
        _api_key: Validated API key — injected by verify_api_key dependency.

    Returns:
        OpenAI-compatible chat completion response.
    """
    logger.info(
        "request.chat_received",
        message_count=len(request.messages),
        model=request.model,
    )

    user_prompt = extract_user_prompt(request.messages)
    history = to_pydantic_history(request.messages)
    deps = AgentDependencies(request_id=get_request_id())

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
