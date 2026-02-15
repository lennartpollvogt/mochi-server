"""Integration tests for chat API endpoints.

Tests the POST /api/v1/chat/{session_id} endpoint with a full app setup,
including session creation, message handling, and error cases.
"""


import pytest
from httpx import AsyncClient



class TestChatNonStreaming:
    """Tests for POST /api/v1/chat/{session_id} endpoint."""

    @pytest.mark.asyncio
    async def test_chat_with_new_message(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test sending a new message and receiving a response."""
        # Create a session first
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        assert response.status_code == 201
        session_id = response.json()["session_id"]

        # Mock Ollama streaming response
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "The"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": " capital"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": " is Paris."},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 10,
                "prompt_eval_count": 50,
            },
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream

        # Send a chat message
        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "What is the capital of France?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["session_id"] == session_id
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "The capital is Paris."
        assert data["message"]["model"] == "llama3.2:latest"
        assert data["message"]["eval_count"] == 10
        assert data["message"]["prompt_eval_count"] == 50
        assert "message_id" in data["message"]
        assert "timestamp" in data["message"]

        # Verify context window info
        assert "context_window" in data
        assert data["context_window"]["current_window"] == 8192
        assert data["context_window"]["usage_tokens"] == 60  # 50 + 10

        # Verify tool calls (empty in Phase 3)
        assert data["tool_calls_executed"] == []

        # Verify messages were persisted
        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is the capital of France?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "The capital is Paris."

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test chat with a session that has a system prompt."""
        # Create session with system prompt
        response = await async_client.post(
            "/api/v1/sessions",
            json={
                "model": "llama3.2:latest",
                "system_prompt": "You are a helpful assistant.",
            },
        )
        assert response.status_code == 201
        session_id = response.json()["session_id"]

        # Mock Ollama response
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "Hello!"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 5,
                "prompt_eval_count": 30,
            },
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream

        # Send message
        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "Hi"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]["content"] == "Hello!"

        # Verify system message is in history
        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        messages = messages_response.json()["messages"]
        assert len(messages) == 3  # system + user + assistant
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_chat_regenerate_without_message(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test re-generating response without providing a new message."""
        # Create session and add a message
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        session_id = response.json()["session_id"]

        # First chat
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "First response"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 5,
                "prompt_eval_count": 20,
            },
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream

        await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "Hello"},
        )

        # Regenerate without new message
        chunks2 = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "Second response"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 6,
                "prompt_eval_count": 21,
            },
        ]

        async def mock_stream2(*args, **kwargs):
            for chunk in chunks2:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream2

        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": None},  # or omit the field
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]["content"] == "Second response"

        # Verify message count
        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        messages = messages_response.json()["messages"]
        # Should have: user, assistant (first), assistant (second)
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_chat_with_nonexistent_session(
        self, async_client: AsyncClient, mock_ollama_client
    ):
        """Test chatting with a session that doesn't exist."""
        response = await async_client.post(
            "/api/v1/chat/nonexistent",
            json={"message": "Hello"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "session_not_found"
        assert "nonexistent" in data["detail"]["error"]["message"]

    @pytest.mark.asyncio
    async def test_chat_ollama_error(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test handling Ollama errors during chat."""
        # Create session
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        session_id = response.json()["session_id"]

        # Mock Ollama error
        async def mock_stream_error(*args, **kwargs):
            raise Exception("Connection refused")
            yield  # Unreachable

        mock_ollama_client.chat_stream = mock_stream_error

        # Send message
        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "Hello"},
        )

        assert response.status_code == 502
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "ollama_error"

    @pytest.mark.asyncio
    async def test_chat_with_think_parameter(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test chat with think parameter (for future Phase support)."""
        # Create session
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        session_id = response.json()["session_id"]

        # Mock response
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "Thinking..."},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 5,
                "prompt_eval_count": 20,
            },
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream

        # Send message with think=true
        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "Complex question", "think": True},
        )

        assert response.status_code == 200
        # In Phase 3, think parameter is accepted but not processed
        assert "message" in response.json()

    @pytest.mark.asyncio
    async def test_chat_multiple_turns(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test multiple back-and-forth chat turns."""
        # Create session
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        session_id = response.json()["session_id"]

        # Turn 1
        chunks1 = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "Hi there!"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 5,
                "prompt_eval_count": 20,
            },
        ]

        async def mock_stream1(*args, **kwargs):
            for chunk in chunks1:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream1

        response1 = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "Hello"},
        )
        assert response1.status_code == 200

        # Turn 2
        chunks2 = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "I'm doing well!"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 6,
                "prompt_eval_count": 30,
            },
        ]

        async def mock_stream2(*args, **kwargs):
            for chunk in chunks2:
                yield chunk

        mock_ollama_client.chat_stream = mock_stream2

        response2 = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "How are you?"},
        )
        assert response2.status_code == 200

        # Verify all messages are saved
        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        messages = messages_response.json()["messages"]
        assert len(messages) == 4  # user1, assistant1, user2, assistant2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "Hi there!"
        assert messages[2]["content"] == "How are you?"
        assert messages[3]["content"] == "I'm doing well!"

    @pytest.mark.asyncio
    async def test_chat_with_empty_session(
        self, async_client: AsyncClient, test_settings, mock_ollama_client
    ):
        """Test chat when message is null and session has no user messages."""
        # Create empty session
        response = await async_client.post(
            "/api/v1/sessions",
            json={"model": "llama3.2:latest"},
        )
        session_id = response.json()["session_id"]

        # Try to chat without providing a message
        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": None},
        )

        # Should fail because there's no message to regenerate from
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "empty_history"
