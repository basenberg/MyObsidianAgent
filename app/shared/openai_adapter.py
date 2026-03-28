"""Bridge between OpenAI message format and Pydantic AI internals.

Converts OpenAI-format chat messages to Pydantic AI ModelMessage history,
and wraps agent output in OpenAI chat completion response shape.
"""

import time
import uuid

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.features.chat.models import ChatMessage, ChatResponse, Choice, ResponseMessage, UsageInfo


def extract_user_prompt(messages: list[ChatMessage]) -> str:
    """Return the content of the last user message.

    Args:
        messages: Full conversation history from the OpenAI request.

    Returns:
        Content of the last user message.

    Raises:
        ValueError: If no user message exists in messages.
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise ValueError("No user message found in messages list.")


def to_pydantic_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Convert OpenAI messages to Pydantic AI ModelMessage history.

    Excludes the last user message — that becomes the user_prompt arg to
    agent.run(). Skips system messages (the agent handles system prompt via
    instructions). Preserves user/assistant turn order.

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
    return history


def to_openai_response(
    content: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> ChatResponse:
    """Wrap agent output text in OpenAI chat completion response shape.

    Args:
        content: The agent's response text.
        prompt_tokens: Input token count from RunUsage.input_tokens.
        completion_tokens: Output token count from RunUsage.output_tokens.

    Returns:
        OpenAI-compatible ChatResponse.
    """
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
