"""Pydantic models for OpenAI-compatible chat completion API."""

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in a chat conversation.

    Attributes:
        role: Sender role — 'user', 'assistant', or 'system'.
        content: Message text content.
    """

    role: str
    content: str


class ChatRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Attributes:
        model: Model identifier (ignored — vault_agent uses its configured model).
        messages: Full conversation history including the latest user message.
        stream: Streaming flag (not supported in MVP — must be False).
    """

    model: str = "paddy"
    messages: list[ChatMessage]
    stream: bool = False


class ResponseMessage(BaseModel):
    """Assistant message in a chat completion response.

    Attributes:
        role: Always 'assistant'.
        content: The agent's response text.
    """

    role: str = "assistant"
    content: str


class Choice(BaseModel):
    """A single completion choice in the response.

    Attributes:
        index: Always 0 (single choice in MVP).
        message: The assistant's response message.
        finish_reason: Always 'stop' for non-streaming.
    """

    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    """Token usage statistics.

    Attributes:
        prompt_tokens: Number of input tokens used.
        completion_tokens: Number of output tokens generated.
        total_tokens: Total tokens (prompt + completion).
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    """OpenAI-compatible chat completion response.

    Attributes:
        id: Unique completion ID (chatcmpl-{uuid}).
        object: Always 'chat.completion'.
        created: Unix timestamp of creation.
        model: Model identifier returned to client.
        choices: List of completion choices (always 1 in MVP).
        usage: Token usage statistics.
    """

    id: str
    object: str = "chat.completion"
    created: int
    model: str = "paddy"
    choices: list[Choice]
    usage: UsageInfo
