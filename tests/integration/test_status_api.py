"""Integration tests for session status API endpoint."""

from unittest.mock import AsyncMock, patch

import pytest

from mochi_server.ollama import ModelInfo


@pytest.fixture(autouse=True)
def mock_ollama_client():
    """Mock OllamaClient for all integration tests."""
    with patch("mochi_server.app.OllamaClient") as mock_client_class:
        # Create the mock instance
        mock_instance = AsyncMock()
        mock_instance.check_connection.return_value = True
        mock_instance.list_models.return_value = [
            ModelInfo(
                name="llama3.2:latest",
                size_mb=4445.3,
                format="gguf",
                family="llama",
                parameter_size="3.2B",
                quantization_level="Q4_0",
                capabilities=["completion"],
                context_length=8192,
            ),
            ModelInfo(
                name="qwen3:14b",
                size_mb=8629.1,
                format="gguf",
                family="qwen2",
                parameter_size="14.8B",
                quantization_level="Q4_K_M",
                capabilities=["completion"],
                context_length=40960,
            ),
        ]
        mock_instance.get_model_info = AsyncMock(
            side_effect=lambda model: ModelInfo(
                name=model,
                size_mb=4445.3,
                format="gguf",
                family="llama",
                parameter_size="3.2B",
                quantization_level="Q4_0",
                capabilities=["completion"],
                context_length=40960 if "qwen" in model else 8192,
            )
        )
        mock_instance.close = AsyncMock()

        mock_client_class.return_value = mock_instance

        yield mock_instance


@pytest.mark.asyncio
async def test_get_session_status_success(async_client):
    """Test successful retrieval of session status."""
    # First create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["model"] == "llama3.2:latest"
    assert data["message_count"] == 0
    assert "context_window" in data
    assert data["context_window"]["dynamic_enabled"] is True
    assert data["context_window"]["current_window"] == 8192
    assert data["context_window"]["model_max_context"] == 8192
    assert data["context_window"]["last_adjustment_reason"] == "initial_setup"
    assert data["context_window"]["manual_override"] is False
    assert data["tools_enabled"] is False
    assert data["active_tools"] == []
    assert data["execution_policy"] == "always_confirm"
    assert data["agents_enabled"] is False
    assert data["enabled_agents"] == []


@pytest.mark.asyncio
async def test_get_session_status_not_found(async_client):
    """Test 404 when session not found."""
    response = await async_client.get("/api/v1/sessions/nonexistent/status")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_status_with_tools(async_client):
    """Test session status includes tool information."""
    # Create a session with tools
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3.2:latest",
            "tool_settings": {
                "tools": ["add_numbers", "get_time"],
                "execution_policy": "always_confirm",
            },
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["tools_enabled"] is True
    assert data["active_tools"] == ["add_numbers", "get_time"]
    assert data["execution_policy"] == "always_confirm"


@pytest.mark.asyncio
async def test_get_session_status_with_agents(async_client):
    """Test session status includes agent information."""
    # Create a session with agents
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3.2:latest",
            "agent_settings": {
                "enabled_agents": ["coder", "agent_builder"],
            },
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["agents_enabled"] is True
    assert data["enabled_agents"] == ["coder", "agent_builder"]


@pytest.mark.asyncio
async def test_get_session_status_with_system_prompt(async_client):
    """Test session status includes system prompt file when system prompt is set directly."""
    # Create a session with a system prompt directly
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3.2:latest",
            "system_prompt": "You are a helpful assistant",
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    # When system_prompt is set directly (not from file), system_prompt_file should be None
    assert data["system_prompt_file"] is None


@pytest.mark.asyncio
async def test_get_session_status_model_max_context(async_client):
    """Test session status includes model max context from different models."""
    # Create a session with qwen model (has larger context)
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "qwen3:14b"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "qwen3:14b"
    assert data["context_window"]["model_max_context"] == 40960


@pytest.mark.asyncio
async def test_get_session_status_after_chat(async_client):
    """Test session status after chat messages."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Send a chat message (will fail due to mocked Ollama, but session state might update)
    # For now just verify initial status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["message_count"] == 0


@pytest.mark.asyncio
async def test_get_session_status_manual_override(async_client):
    """Test session status with manual context window override."""
    # This would require updating the session's context_window_config
    # For now just verify the initial status has correct defaults
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Get session status
    response = await async_client.get(f"/api/v1/sessions/{session_id}/status")

    assert response.status_code == 200
    data = response.json()
    # Default values
    assert data["context_window"]["dynamic_enabled"] is True
    assert data["context_window"]["manual_override"] is False
