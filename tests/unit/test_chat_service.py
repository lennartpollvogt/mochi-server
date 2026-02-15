"""Unit tests for chat service functionality.

Tests the core chat logic including message conversion, response collection,
and error handling.
"""

from unittest.mock import AsyncMock

import pytest

from mochi_server.routers.chat import (
    _collect_streaming_response,
    _convert_messages_to_ollama_format,
)
from mochi_server.sessions.types import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)


class TestMessageConversion:
    """Tests for converting session messages to Ollama format."""

    def test_convert_empty_list(self):
        """Test converting an empty message list."""
        result = _convert_messages_to_ollama_format([])
        assert result == []

    def test_convert_user_message(self):
        """Test converting a user message."""
        msg = UserMessage(
            content="Hello!",
            message_id="msg1",
            timestamp="2024-01-01T10:00:00Z",
        )
        result = _convert_messages_to_ollama_format([msg])

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello!"

    def test_convert_system_message(self):
        """Test converting a system message."""
        msg = SystemMessage(
            content="You are helpful",
            message_id="msg1",
            timestamp="2024-01-01T10:00:00Z",
        )
        result = _convert_messages_to_ollama_format([msg])

        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful"

    def test_convert_assistant_message_without_tool_calls(self):
        """Test converting an assistant message without tool calls."""
        msg = AssistantMessage(
            content="Hi there!",
            model="llama3.2:latest",
            message_id="msg1",
            timestamp="2024-01-01T10:00:00Z",
        )
        result = _convert_messages_to_ollama_format([msg])

        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hi there!"
        assert "tool_calls" not in result[0]

    def test_convert_assistant_message_with_tool_calls(self):
        """Test converting an assistant message with tool calls."""
        tool_calls = [{"function": {"name": "calculator", "arguments": {"a": 1}}}]
        msg = AssistantMessage(
            content="Let me calculate",
            model="llama3.2:latest",
            message_id="msg1",
            timestamp="2024-01-01T10:00:00Z",
            tool_calls=tool_calls,
        )
        result = _convert_messages_to_ollama_format([msg])

        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"] == tool_calls

    def test_convert_multiple_messages(self):
        """Test converting a conversation with multiple messages."""
        messages = [
            SystemMessage(
                content="You are helpful",
                message_id="msg1",
                timestamp="2024-01-01T10:00:00Z",
            ),
            UserMessage(
                content="Hello",
                message_id="msg2",
                timestamp="2024-01-01T10:01:00Z",
            ),
            AssistantMessage(
                content="Hi!",
                model="llama3.2:latest",
                message_id="msg3",
                timestamp="2024-01-01T10:01:05Z",
            ),
        ]
        result = _convert_messages_to_ollama_format(messages)

        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"


class TestStreamingResponseCollection:
    """Tests for collecting streaming responses from Ollama."""

    @pytest.mark.asyncio
    async def test_collect_complete_response(self):
        """Test collecting a complete streaming response."""
        # Mock streaming chunks
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

        # Mock the client
        mock_client = AsyncMock()

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_client.chat_stream = mock_stream

        # Collect the response
        content, final_chunk = await _collect_streaming_response(
            mock_client,
            model="llama3.2:latest",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert content == "Hello there!"
        assert final_chunk["done"] is True
        assert final_chunk["eval_count"] == 10
        assert final_chunk["prompt_eval_count"] == 50

    @pytest.mark.asyncio
    async def test_collect_response_with_empty_chunks(self):
        """Test collecting response when some chunks have empty content."""
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "OK"},
                "done": False,
            },
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "eval_count": 5,
            },
        ]

        mock_client = AsyncMock()

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_client.chat_stream = mock_stream

        content, final_chunk = await _collect_streaming_response(
            mock_client,
            model="llama3.2:latest",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert content == "OK"
        assert final_chunk["done"] is True

    @pytest.mark.asyncio
    async def test_collect_response_ollama_error(self):
        """Test handling Ollama streaming errors."""
        mock_client = AsyncMock()

        async def mock_stream(*args, **kwargs):
            raise Exception("Connection refused")
            yield  # Unreachable, but makes this a generator

        mock_client.chat_stream = mock_stream

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await _collect_streaming_response(
                mock_client,
                model="llama3.2:latest",
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert exc_info.value.status_code == 502
        assert "ollama_error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_collect_response_no_done_marker(self):
        """Test handling response without done marker."""
        chunks = [
            {
                "model": "llama3.2:latest",
                "message": {"role": "assistant", "content": "Hello"},
                "done": False,
            },
            # Missing final chunk with done=True
        ]

        mock_client = AsyncMock()

        async def mock_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk

        mock_client.chat_stream = mock_stream

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await _collect_streaming_response(
                mock_client,
                model="llama3.2:latest",
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert exc_info.value.status_code == 502
        assert "incomplete_response" in str(exc_info.value.detail)
