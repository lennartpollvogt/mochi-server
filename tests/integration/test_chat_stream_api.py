"""Integration tests for streaming chat API endpoints.

This module tests the SSE streaming chat endpoint including:
- Basic streaming with content deltas
- Message persistence after streaming
- Client disconnection handling
- Error scenarios
- Message regeneration after editing
"""

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_stream_chat_basic(async_client: AsyncClient, mock_ollama_client):
    """Test basic streaming chat response."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Mock streaming response
    chunks = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "Hello"},
            "done": False,
        },
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": " there"},
            "done": False,
        },
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "!"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream

    # Stream a message
    response = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Hi!"},
    )
    assert response.status_code == 200

    # Parse SSE events
    events = []
    # Normalize line endings and split by double newline
    normalized_text = response.text.replace("\r\n", "\n")
    chunks = normalized_text.strip().split("\n\n")
    for line in chunks:
        if line.strip():  # Skip empty chunks
            event_type = None
            event_data = None
            for part in line.split("\n"):
                if part.startswith("event:"):
                    event_type = part.split(":", 1)[1].strip()
                elif part.startswith("data:"):
                    event_data = part.split(":", 1)[1].strip()
            if event_type and event_data:
                events.append({"event": event_type, "data": json.loads(event_data)})

    # Verify event sequence
    assert len(events) >= 3  # At least content_deltas + message_complete + done

    # Check content deltas
    content_events = [e for e in events if e["event"] == "content_delta"]
    assert len(content_events) == 3
    assert content_events[0]["data"]["content"] == "Hello"
    assert content_events[1]["data"]["content"] == " there"
    assert content_events[2]["data"]["content"] == "!"

    # Check message_complete event
    complete_events = [e for e in events if e["event"] == "message_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["data"]["model"] == "llama3.2:latest"
    assert complete_events[0]["data"]["eval_count"] == 5
    assert complete_events[0]["data"]["prompt_eval_count"] == 20

    # Check done event
    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["data"]["session_id"] == session_id

    # Verify message was saved to session
    session_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["message_count"] == 2  # user + assistant (no system prompt)

    messages = session_data["messages"]
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "Hello there!"


@pytest.mark.asyncio
async def test_stream_chat_regenerate(async_client: AsyncClient, mock_ollama_client):
    """Test streaming chat regeneration without new user message."""
    # Create a session and add a message
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # First message
    chunks1 = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "First response"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream1(*args, **kwargs):
        for chunk in chunks1:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream1

    response1 = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Hi"},
    )
    assert response1.status_code == 200

    # Regenerate (message=null)
    chunks2 = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "Second response"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream2(*args, **kwargs):
        for chunk in chunks2:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream2

    response2 = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": None},
    )
    assert response2.status_code == 200

    # Verify both messages are in session
    session_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    session_data = session_response.json()
    # user + assistant + assistant (regenerated, no system prompt)
    assert session_data["message_count"] == 3


@pytest.mark.asyncio
async def test_stream_chat_session_not_found(async_client: AsyncClient):
    """Test streaming chat with non-existent session."""
    response = await async_client.post(
        "/api/v1/chat/nonexistent/stream",
        json={"message": "Hi"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_chat_ollama_error(async_client: AsyncClient, mock_ollama_client):
    """Test streaming chat when Ollama fails."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Mock Ollama error
    async def mock_chat_stream_error(*args, **kwargs):
        raise Exception("Ollama error")
        yield  # Make it a generator

    mock_ollama_client.chat_stream = mock_chat_stream_error

    # Stream a message
    response = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Hi!"},
    )
    assert response.status_code == 200

    # Parse SSE events
    events = []
    # Normalize line endings and split by double newline
    normalized_text = response.text.replace("\r\n", "\n")
    chunks = normalized_text.strip().split("\n\n")
    for line in chunks:
        if line.strip():  # Skip empty chunks
            event_type = None
            event_data = None
            for part in line.split("\n"):
                if part.startswith("event:"):
                    event_type = part.split(":", 1)[1].strip()
                elif part.startswith("data:"):
                    event_data = part.split(":", 1)[1].strip()
            if event_type and event_data:
                events.append({"event": event_type, "data": json.loads(event_data)})

    # Should have error event
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "ollama_error"


@pytest.mark.asyncio
async def test_stream_chat_with_system_prompt(
    async_client: AsyncClient, mock_ollama_client
):
    """Test streaming chat with system prompt."""
    # Create a session with system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={
            "model": "llama3.2:latest",
            "system_prompt": "You are a helpful assistant.",
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Mock streaming response
    chunks = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "I'm here to help!"},
            "done": True,
            "eval_count": 10,
            "prompt_eval_count": 25,
        },
    ]

    async def mock_chat_stream(*args, **kwargs):
        # Verify system prompt is in messages
        messages = kwargs.get("messages", [])
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        for chunk in chunks:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream

    # Stream a message
    response = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Hello"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_stream_chat_empty_history(async_client: AsyncClient):
    """Test streaming chat with empty session (no messages)."""
    # Create a session without system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest", "system_prompt": None},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Try to regenerate without any messages
    response = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": None},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_message(async_client: AsyncClient, mock_ollama_client):
    """Test editing a message and truncating subsequent messages."""
    # Create a session and add messages
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Add first message
    chunks = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "Original response"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream

    await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Original question"},
    )

    # Verify we have 2 messages (user + assistant, no system prompt provided)
    session_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.json()["message_count"] == 2

    # Edit the user message (index 0, no system prompt in this session)
    edit_response = await async_client.put(
        f"/api/v1/sessions/{session_id}/messages/0",
        json={"content": "Edited question"},
    )
    assert edit_response.status_code == 200

    # Verify message was edited and assistant message was truncated
    session_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    session_data = session_response.json()
    assert session_data["message_count"] == 1  # edited user only
    assert session_data["messages"][0]["content"] == "Edited question"


@pytest.mark.asyncio
async def test_edit_message_not_found(async_client: AsyncClient):
    """Test editing message in non-existent session."""
    response = await async_client.put(
        "/api/v1/sessions/nonexistent/messages/0",
        json={"content": "New content"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_edit_message_invalid_index(async_client: AsyncClient):
    """Test editing message with invalid index."""
    # Create a session
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Try to edit out of range index
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/messages/99",
        json={"content": "New content"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_non_user_message(async_client: AsyncClient):
    """Test editing a non-user message (should fail)."""
    # Create a session with system prompt
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest", "system_prompt": "You are helpful."},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # Try to edit system message (index 0)
    response = await async_client.put(
        f"/api/v1/sessions/{session_id}/messages/0",
        json={"content": "New system prompt"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_and_regenerate(async_client: AsyncClient, mock_ollama_client):
    """Test full flow: edit message and regenerate response."""
    # Create a session and add message
    create_response = await async_client.post(
        "/api/v1/sessions",
        json={"model": "llama3.2:latest"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]

    # First message
    chunks1 = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "Original"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream1(*args, **kwargs):
        for chunk in chunks1:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream1

    await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={"message": "Question 1"},
    )

    # Edit the user message (index 0, no system prompt)
    await async_client.put(
        f"/api/v1/sessions/{session_id}/messages/0",
        json={"content": "Question 2"},
    )

    # Regenerate with new question
    chunks2 = [
        {
            "model": "llama3.2:latest",
            "message": {"role": "assistant", "content": "New response"},
            "done": True,
            "eval_count": 5,
            "prompt_eval_count": 20,
        },
    ]

    async def mock_chat_stream2(*args, **kwargs):
        for chunk in chunks2:
            yield chunk

    mock_ollama_client.chat_stream = mock_chat_stream2

    response = await async_client.post(
        f"/api/v1/chat/{session_id}/stream",
        json={},  # No message - regenerate from current history
    )
    assert response.status_code == 200

    # Verify final state
    session_response = await async_client.get(f"/api/v1/sessions/{session_id}")
    session_data = session_response.json()
    assert (
        session_data["message_count"] == 2
    )  # edited user + new assistant (no system prompt)
    assert session_data["messages"][0]["content"] == "Question 2"
    assert session_data["messages"][1]["content"] == "New response"
