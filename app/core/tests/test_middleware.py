"""Tests for app.core.middleware module."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import setup_middleware


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application."""
    test_app = FastAPI()

    @test_app.get("/test")
    def test_endpoint() -> dict[str, str]:
        return {"message": "test"}

    @test_app.get("/error")
    def error_endpoint() -> None:
        raise ValueError("Test error")

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client with middleware."""
    setup_middleware(app)
    return TestClient(app)


def test_middleware_generates_request_id(client: TestClient) -> None:
    """Test middleware generates request_id if not provided."""
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_middleware_uses_provided_request_id(client: TestClient) -> None:
    """Test middleware uses X-Request-ID header if provided."""
    test_request_id = "test-request-id-123"

    response = client.get("/test", headers={"X-Request-ID": test_request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == test_request_id


def test_middleware_logs_request_started(client: TestClient) -> None:
    """Test middleware logs request.http_received event."""
    with patch("app.core.middleware.logger") as mock_logger:
        response = client.get("/test")

        assert response.status_code == 200
        # Check that logger.info was called with request.http_received
        mock_logger.info.assert_any_call(
            "request.http_received",
            method="GET",
            path="/test",
            client_host="testclient",
        )


def test_middleware_logs_request_completed(client: TestClient) -> None:
    """Test middleware logs request.http_completed with status and duration."""
    with patch("app.core.middleware.logger") as mock_logger:
        response = client.get("/test")

        assert response.status_code == 200
        # Find the call with request.http_completed
        completed_call = None
        for call in mock_logger.info.call_args_list:
            if call[0][0] == "request.http_completed":
                completed_call = call
                break

        assert completed_call is not None
        _, kwargs = completed_call
        assert kwargs["method"] == "GET"
        assert kwargs["path"] == "/test"
        assert kwargs["status_code"] == 200
        assert "duration_seconds" in kwargs
        assert isinstance(kwargs["duration_seconds"], float)


def test_middleware_logs_request_failed_on_exception(client: TestClient) -> None:
    """Test middleware logs request.http_failed with exc_info on exceptions."""
    with patch("app.core.middleware.logger") as mock_logger:
        with pytest.raises(ValueError):
            client.get("/error")

        # Check that logger.error was called with request.http_failed
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "request.http_failed"
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/error"
        assert call_args[1]["error"] == "Test error"
        assert call_args[1]["exc_info"] is True
        assert "duration_seconds" in call_args[1]


def test_middleware_adds_request_id_to_response(client: TestClient) -> None:
    """Test X-Request-ID is added to all response headers."""
    response = client.get("/test")

    assert "X-Request-ID" in response.headers


def test_setup_middleware_adds_cors(app: FastAPI) -> None:
    """Test setup_middleware adds CORS middleware."""
    setup_middleware(app)

    # Check middleware was added
    # FastAPI stores middleware in app.user_middleware
    # We verify by checking that middleware count increased
    assert len(app.user_middleware) >= 2  # At least RequestLogging and CORS

    # Verify that middleware is working by checking response headers
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
