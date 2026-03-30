"""Unit tests for SSE streaming branch of app.features.chat.routes."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_STREAM_HEADERS = {"Authorization": "Bearer test-bearer-token"}
_STREAM_PAYLOAD = {"messages": [{"role": "user", "content": "Say hello"}], "stream": True}


@asynccontextmanager
async def _mock_iter_empty(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Context manager mock for vault_agent.iter that yields no nodes."""
    mock_run = MagicMock()
    mock_run.__aiter__ = MagicMock(return_value=iter([]))
    yield mock_run


@pytest.mark.unit
def test_streaming_returns_event_stream_content_type(app_client: TestClient) -> None:
    """Verify Content-Type is text/event-stream when stream=True."""
    with patch("app.features.chat.routes.vault_agent.iter", new=_mock_iter_empty):
        with app_client.stream(
            "POST", "/v1/chat/completions", json=_STREAM_PAYLOAD, headers=_STREAM_HEADERS
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.unit
def test_streaming_response_contains_done_terminator(app_client: TestClient) -> None:
    """Verify response body ends with data: [DONE] terminator."""
    with patch("app.features.chat.routes.vault_agent.iter", new=_mock_iter_empty):
        with app_client.stream(
            "POST", "/v1/chat/completions", json=_STREAM_PAYLOAD, headers=_STREAM_HEADERS
        ) as response:
            body = response.read().decode()
    assert "data: [DONE]" in body


@pytest.mark.unit
def test_streaming_chunks_have_required_fields(app_client: TestClient) -> None:
    """Verify at least one SSE chunk has id, object, and choices[0].delta fields."""
    with patch("app.features.chat.routes.vault_agent.iter", new=_mock_iter_empty):
        with app_client.stream(
            "POST", "/v1/chat/completions", json=_STREAM_PAYLOAD, headers=_STREAM_HEADERS
        ) as response:
            body = response.read().decode()

    # Parse all data: lines that contain JSON
    chunks = []
    for line in body.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            chunks.append(json.loads(line[len("data: ") :]))

    assert len(chunks) >= 1
    first = chunks[0]
    assert "id" in first
    assert first.get("object") == "chat.completion.chunk"
    assert "choices" in first
    assert len(first["choices"]) == 1
    assert "delta" in first["choices"][0]


@pytest.mark.unit
def test_streaming_requires_auth(app_client: TestClient) -> None:
    """Verify 403 is returned when Authorization header is missing for streaming."""
    response = app_client.post(
        "/v1/chat/completions",
        json=_STREAM_PAYLOAD,
    )
    assert response.status_code == 403


@pytest.mark.unit
def test_non_streaming_still_works_when_stream_false(app_client: TestClient) -> None:
    """Verify stream=False still returns standard chat.completion JSON object."""
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
            json={"messages": [{"role": "user", "content": "Hello"}], "stream": False},
            headers=_STREAM_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello from Paddy!"
