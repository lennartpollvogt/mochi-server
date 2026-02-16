"""Integration tests for session API endpoints.

Tests the full session CRUD API with httpx AsyncClient against
the FastAPI application.
"""

from unittest.mock import AsyncMock, patch

import pytest

from mochi_server.ollama import ModelInfo


@pytest.fixture(autouse=True)
def mock_ollama_client():
    """Mock OllamaClient for all integration tests.

    This fixture patches the OllamaClient class before the app is created,
    ensuring the lifespan uses our mock instead of creating a real client.
    """
    with patch("mochi_server.app.OllamaClient") as mock_client_class:
        # Create the mock instance
        mock_instance = AsyncMock()
        mock_instance.check_connection.return_value = True
        mock_instance.list_models.return_value = [
            ModelInfo(
                name="llama3:8b",
                size_mb=4445.3,
                format="gguf",
                family="llama",
                parameter_size="8.0B",
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
                context_length=32768,
            ),
        ]
        mock_instance.get_model_info.return_value = ModelInfo(
            name="llama3:8b",
            size_mb=4445.3,
            format="gguf",
            family="llama",
            parameter_size="8.0B",
            quantization_level="Q4_0",
            capabilities=["completion"],
            context_length=8192,
        )
        mock_instance.close = AsyncMock()

        # Make the class return our mock instance
        mock_client_class.return_value = mock_instance

        yield mock_instance


@pytest.mark.asyncio
async def test_create_session(async_client):
    """Test creating a new session."""
    response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )

    assert response.status_code == 201
    data = response.json()

    assert "session_id" in data
    assert len(data["session_id"]) == 10
    assert data["model"] == "llama3:8b"
    assert data["message_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data
    assert "tool_settings" in data
    assert "agent_settings" in data


@pytest.mark.asyncio
async def test_create_session_with_system_prompt(async_client):
    """Test creating a session with a system prompt."""
    response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": "You are a helpful assistant",
            "system_prompt_source_file": "helpful.md",
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["message_count"] == 1


@pytest.mark.asyncio
async def test_create_session_with_tool_settings(async_client):
    """Test creating a session with tool settings."""
    response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "tool_settings": {
                "tools": ["tool1", "tool2"],
                "tool_group": "math",
                "execution_policy": "never_confirm",
            },
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["tool_settings"]["tools"] == ["tool1", "tool2"]
    assert data["tool_settings"]["tool_group"] == "math"
    assert data["tool_settings"]["execution_policy"] == "never_confirm"


@pytest.mark.asyncio
async def test_create_session_with_agent_settings(async_client):
    """Test creating a session with agent settings."""
    response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "agent_settings": {
                "enabled_agents": ["coder", "researcher"],
            },
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["agent_settings"]["enabled_agents"] == ["coder", "researcher"]


@pytest.mark.asyncio
async def test_create_session_invalid_model(async_client, mock_ollama_client, test_app):
    """Test creating a session with invalid model returns 400."""
    # Mock get_model_info to return None (model not found)
    test_app.state.ollama_client.get_model_info.return_value = None

    response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "invalid:model"},
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()

    # Reset mock for other tests
    test_app.state.ollama_client.get_model_info.return_value = ModelInfo(
        name="llama3:8b",
        size_mb=4445.3,
        format="gguf",
        family="llama",
        parameter_size="8.0B",
        quantization_level="Q4_0",
        capabilities=["completion"],
        context_length=8192,
    )


@pytest.mark.asyncio
async def test_list_sessions_empty(async_client):
    """Test listing sessions when none exist."""
    response = await async_client.get("/api/v1/sessions")

    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert data["sessions"] == []


@pytest.mark.asyncio
async def test_list_sessions(async_client):
    """Test listing multiple sessions."""
    # Create sessions
    session_ids = []
    for i in range(3):
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3:8b"},
        )
        assert response.status_code == 201
        session_ids.append(response.json()["session_id"])

    # List them
    response = await async_client.get("/api/v1/sessions")

    assert response.status_code == 200
    data = response.json()

    assert len(data["sessions"]) == 3
    listed_ids = [s["session_id"] for s in data["sessions"]]
    for session_id in session_ids:
        assert session_id in listed_ids


@pytest.mark.asyncio
async def test_list_sessions_includes_preview(async_client):
    """Test that list_sessions includes preview field."""
    # Create a session
    response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    assert response.status_code == 201

    # List sessions
    response = await async_client.get("/api/v1/sessions")

    assert response.status_code == 200
    data = response.json()

    assert len(data["sessions"]) == 1
    session = data["sessions"][0]
    assert "preview" in session
    assert session["preview"] == ""  # No messages yet


@pytest.mark.asyncio
async def test_get_session(async_client):
    """Test retrieving a specific session."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Retrieve it
    response = await async_client.get(f"/api/v1/sessions/{session_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["model"] == "llama3:8b"
    assert "messages" in data
    assert data["messages"] == []
    assert "tool_settings" in data
    assert "agent_settings" in data


@pytest.mark.asyncio
async def test_get_session_not_found(async_client):
    """Test retrieving a nonexistent session returns 404."""
    response = await async_client.get("/api/v1/sessions/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_session_with_messages(async_client, test_settings):
    """Test retrieving a session with messages."""
    # Create session manually with messages
    from datetime import datetime, timezone

    from mochi_server.sessions import ChatSession, UserMessage

    # Use the same sessions_dir as the app
    sessions_dir = test_settings.resolved_sessions_dir

    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.save(sessions_dir)

    # Retrieve via API
    response = await async_client.get("/api/v1/sessions/test123")

    assert response.status_code == 200
    data = response.json()

    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_delete_session(async_client):
    """Test deleting a session."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Delete it
    response = await async_client.delete(f"/api/v1/sessions/{session_id}")

    assert response.status_code == 204

    # Verify it's gone
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_not_found(async_client):
    """Test deleting a nonexistent session returns 404."""
    response = await async_client.delete("/api/v1/sessions/nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_session_model(async_client, test_app):
    """Test updating a session's model."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Mock the new model
    test_app.state.ollama_client.get_model_info.return_value = ModelInfo(
        name="qwen3:14b",
        size_mb=8629.1,
        format="gguf",
        family="qwen2",
        parameter_size="14.8B",
        quantization_level="Q4_K_M",
        capabilities=["completion"],
        context_length=32768,
    )

    # Update model
    response = await async_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"model": "qwen3:14b"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["model"] == "qwen3:14b"

    # Verify via get
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.json()["model"] == "qwen3:14b"


@pytest.mark.asyncio
async def test_update_session_tool_settings(async_client):
    """Test updating session tool settings."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Update tool settings
    response = await async_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={
            "tool_settings": {
                "tools": ["new_tool"],
                "tool_group": "utilities",
                "execution_policy": "auto",
            }
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["tool_settings"]["tools"] == ["new_tool"]
    assert data["tool_settings"]["tool_group"] == "utilities"
    assert data["tool_settings"]["execution_policy"] == "auto"


@pytest.mark.asyncio
async def test_update_session_agent_settings(async_client):
    """Test updating session agent settings."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Update agent settings
    response = await async_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"agent_settings": {"enabled_agents": ["agent1", "agent2"]}},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["agent_settings"]["enabled_agents"] == ["agent1", "agent2"]


@pytest.mark.asyncio
async def test_update_session_invalid_model(async_client, test_app):
    """Test updating to invalid model returns 400."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Mock invalid model
    test_app.state.ollama_client.get_model_info.return_value = None

    # Attempt update
    response = await async_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"model": "invalid:model"},
    )

    assert response.status_code == 400

    # Reset mock for other tests
    test_app.state.ollama_client.get_model_info.return_value = ModelInfo(
        name="llama3:8b",
        size_mb=4445.3,
        format="gguf",
        family="llama",
        parameter_size="8.0B",
        quantization_level="Q4_0",
        capabilities=["completion"],
        context_length=8192,
    )


@pytest.mark.asyncio
async def test_update_session_not_found(async_client):
    """Test updating a nonexistent session returns 404."""
    response = await async_client.patch(
        "/api/v1/sessions/nonexistent",
        json={"model": "llama3:8b"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_messages(async_client, test_settings):
    """Test getting messages from a session."""
    # Create session with messages
    from datetime import datetime, timezone

    from mochi_server.sessions import ChatSession, UserMessage

    # Use the same sessions_dir as the app
    sessions_dir = test_settings.resolved_sessions_dir

    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(UserMessage(content="World", message_id="msg2", timestamp=now))
    session.save(sessions_dir)

    # Get messages via API
    response = await async_client.get("/api/v1/sessions/test123/messages")

    assert response.status_code == 200
    data = response.json()

    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][1]["content"] == "World"


@pytest.mark.asyncio
async def test_get_messages_not_found(async_client):
    """Test getting messages from nonexistent session returns 404."""
    response = await async_client.get("/api/v1/sessions/nonexistent/messages")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_workflow(async_client):
    """Test a complete workflow: create multiple sessions and list them."""
    # Create sessions with different models
    response1 = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    assert response1.status_code == 201
    session1_id = response1.json()["session_id"]

    response2 = await async_client.post(
        "/api/v1/sessions",
        json={"model": "qwen3:14b"},
    )
    assert response2.status_code == 201
    session2_id = response2.json()["session_id"]

    # List all sessions
    list_response = await async_client.get("/api/v1/sessions")
    assert list_response.status_code == 200

    sessions = list_response.json()["sessions"]
    assert len(sessions) == 2

    # Verify both sessions are in the list
    session_ids = [s["session_id"] for s in sessions]
    assert session1_id in session_ids
    assert session2_id in session_ids


@pytest.mark.asyncio
async def test_update_multiple_fields(async_client, test_app):
    """Test updating multiple fields at once."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Mock the new model
    test_app.state.ollama_client.get_model_info.return_value = ModelInfo(
        name="qwen3:14b",
        size_mb=8629.1,
        format="gguf",
        family="qwen2",
        parameter_size="14.8B",
        quantization_level="Q4_K_M",
        capabilities=["completion"],
        context_length=32768,
    )

    # Update multiple fields
    response = await async_client.patch(
        f"/api/v1/sessions/{session_id}",
        json={
            "model": "qwen3:14b",
            "tool_settings": {
                "tools": ["tool1"],
                "tool_group": None,
                "execution_policy": "always_confirm",
            },
            "agent_settings": {"enabled_agents": ["agent1"]},
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["model"] == "qwen3:14b"
    assert data["tool_settings"]["tools"] == ["tool1"]
    assert data["agent_settings"]["enabled_agents"] == ["agent1"]


@pytest.mark.asyncio
async def test_set_session_system_prompt(async_client, test_app, mock_ollama_client):
    """Test setting a system prompt on a session."""
    # Create session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Set system prompt
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/system-prompt",
        json={
            "content": "You are a helpful assistant.",
            "source_file": "helpful.md",
        },
    )

    assert response.status_code == 200

    # Verify system prompt was added
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][0]["content"] == "You are a helpful assistant."
    assert data["messages"][0]["source_file"] == "helpful.md"


@pytest.mark.asyncio
async def test_set_session_system_prompt_without_source_file(
    async_client, test_app, mock_ollama_client
):
    """Test setting a system prompt without source file."""
    # Create session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Set system prompt without source file
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/system-prompt",
        json={"content": "You are a helpful assistant."},
    )

    assert response.status_code == 200

    # Verify system prompt was added
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][0]["source_file"] is None


@pytest.mark.asyncio
async def test_update_session_system_prompt(async_client, test_app, mock_ollama_client):
    """Test updating an existing system prompt."""
    # Create session with system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": "Old prompt",
            "system_prompt_source_file": "old.md",
        },
    )
    session_id = create_response.json()["session_id"]

    # Update system prompt
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/system-prompt",
        json={
            "content": "New prompt",
            "source_file": "new.md",
        },
    )

    assert response.status_code == 200

    # Verify system prompt was updated
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][0]["content"] == "New prompt"
    assert data["messages"][0]["source_file"] == "new.md"


@pytest.mark.asyncio
async def test_set_system_prompt_on_session_with_messages(
    async_client, test_app, mock_ollama_client
):
    """Test that setting system prompt on a session that already has messages inserts at index 0."""
    # Create session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Manually add a user message using edit endpoint
    # (avoiding chat to work around mock issues)
    from datetime import datetime, timezone

    from mochi_server.sessions import ChatSession, UserMessage

    settings = test_app.state.settings
    session = ChatSession.load(session_id, settings.resolved_sessions_dir)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.save(settings.resolved_sessions_dir)

    # Set system prompt
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/system-prompt",
        json={"content": "You are helpful"},
    )

    assert response.status_code == 200

    # Verify system prompt was inserted at index 0 and user message preserved
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert len(data["messages"]) == 2  # system, user
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][0]["content"] == "You are helpful"
    assert data["messages"][1]["role"] == "user"
    assert data["messages"][1]["content"] == "Hello"


@pytest.mark.asyncio
async def test_remove_session_system_prompt(async_client, test_app, mock_ollama_client):
    """Test removing a system prompt from a session."""
    # Create session with system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": "You are helpful",
        },
    )
    session_id = create_response.json()["session_id"]

    # Remove system prompt
    response = await async_client.delete(f"/api/v1/sessions/{session_id}/system-prompt")

    assert response.status_code == 204

    # Verify system prompt was removed
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert len(data["messages"]) == 0


@pytest.mark.asyncio
async def test_remove_system_prompt_with_other_messages(
    async_client, test_app, mock_ollama_client
):
    """Test removing system prompt preserves other messages."""
    # Create session with system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": "You are helpful",
        },
    )
    session_id = create_response.json()["session_id"]

    # Manually add a user message
    from datetime import datetime, timezone

    from mochi_server.sessions import ChatSession, UserMessage

    settings = test_app.state.settings
    session = ChatSession.load(session_id, settings.resolved_sessions_dir)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.save(settings.resolved_sessions_dir)

    # Remove system prompt
    response = await async_client.delete(f"/api/v1/sessions/{session_id}/system-prompt")

    assert response.status_code == 204

    # Verify user message was preserved
    get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    data = get_response.json()
    assert len(data["messages"]) == 1  # only user message (no system)
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_remove_system_prompt_none_exists(
    async_client, test_app, mock_ollama_client
):
    """Test removing system prompt when none exists returns 400."""
    # Create session without system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3:8b"},
    )
    session_id = create_response.json()["session_id"]

    # Try to remove system prompt
    response = await async_client.delete(f"/api/v1/sessions/{session_id}/system-prompt")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_set_system_prompt_session_not_found(async_client, test_app):
    """Test setting system prompt on non-existent session returns 404."""
    response = await async_client.put(
        "/api/v1/sessions/nonexistent/system-prompt",
        json={"content": "You are helpful"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_remove_system_prompt_session_not_found(async_client, test_app):
    """Test removing system prompt from non-existent session returns 404."""
    response = await async_client.delete("/api/v1/sessions/nonexistent/system-prompt")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_session_with_system_prompt_from_file(async_client, test_app):
    """Test creating a session with system prompt loaded from file."""
    # Create a system prompt file
    await async_client.post(
        "/api/v1/system-prompts",
        json={
            "filename": "helpful.md",
            "content": "You are a helpful assistant from file.",
        },
    )

    # Create session with only source_file (no content)
    response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": None,
            "system_prompt_source_file": "helpful.md",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message_count"] == 1

    # Verify the system prompt was loaded from file
    session_response = await async_client.get(f"/api/v1/sessions/{data['session_id']}")
    session_data = session_response.json()
    assert len(session_data["messages"]) == 1
    assert session_data["messages"][0]["role"] == "system"
    assert session_data["messages"][0]["content"] == "You are a helpful assistant from file."
    assert session_data["messages"][0]["source_file"] == "helpful.md"


@pytest.mark.asyncio
async def test_create_session_with_nonexistent_system_prompt_file(async_client):
    """Test creating a session with nonexistent system prompt file returns 404."""
    response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3:8b",
            "system_prompt": None,
            "system_prompt_source_file": "nonexistent.md",
        },
    )

    assert response.status_code == 404
