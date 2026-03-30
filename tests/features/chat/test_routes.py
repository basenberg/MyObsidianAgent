"""Unit tests for app.features.chat.routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_chat_requires_auth(app_client: TestClient) -> None:
    """Test /v1/chat/completions returns 403 when Authorization header is missing."""
    response = app_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_chat_rejects_invalid_key(app_client: TestClient) -> None:
    """Test /v1/chat/completions returns 401 for an incorrect Bearer token."""
    response = app_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.unit
def test_chat_returns_openai_format(app_client: TestClient) -> None:
    """Test that a valid request returns a complete OpenAI-format response."""
    mock_result = MagicMock()
    mock_result.output = "Hello from Paddy!"
    mock_usage = MagicMock()
    mock_usage.input_tokens = 10
    mock_usage.output_tokens = 5
    mock_result.usage.return_value = mock_usage

    with patch("app.features.chat.routes.vault_agent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        response = app_client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Say hello"}], "stream": False},
            headers={"Authorization": "Bearer test-bearer-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello from Paddy!"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["id"].startswith("chatcmpl-")
    assert "usage" in data


@pytest.mark.unit
def test_chat_with_conversation_history(app_client: TestClient) -> None:
    """Test multi-turn conversation history is accepted without error."""
    mock_result = MagicMock()
    mock_result.output = "Context retained."
    mock_usage = MagicMock()
    mock_usage.input_tokens = 20
    mock_usage.output_tokens = 5
    mock_result.usage.return_value = mock_usage

    with patch("app.features.chat.routes.vault_agent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        response = app_client.post(
            "/v1/chat/completions",
            json={
                "messages": [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "First response"},
                    {"role": "user", "content": "Follow-up question"},
                ],
                "stream": False,
            },
            headers={"Authorization": "Bearer test-bearer-token"},
        )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Context retained."


@pytest.mark.unit
def test_extract_user_prompt_returns_last_user_message() -> None:
    """Test extract_user_prompt returns the last user message content."""
    from app.features.chat.models import ChatMessage
    from app.shared.openai_adapter import extract_user_prompt

    messages = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="response"),
        ChatMessage(role="user", content="last user message"),
    ]
    assert extract_user_prompt(messages) == "last user message"


@pytest.mark.unit
def test_extract_user_prompt_raises_on_no_user_message() -> None:
    """Test extract_user_prompt raises ValueError if no user message found."""
    from app.features.chat.models import ChatMessage
    from app.shared.openai_adapter import extract_user_prompt

    with pytest.raises(ValueError, match="No user message found"):
        extract_user_prompt([ChatMessage(role="assistant", content="only assistant")])


@pytest.mark.unit
def test_to_pydantic_history_excludes_last_user_message() -> None:
    """Test to_pydantic_history excludes the last user message from history."""
    from app.features.chat.models import ChatMessage
    from app.shared.openai_adapter import to_pydantic_history

    messages = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="reply"),
        ChatMessage(role="user", content="last — should be excluded"),
    ]
    history = to_pydantic_history(messages)
    # Should contain first user + assistant, but not the last user message
    assert len(history) == 2
