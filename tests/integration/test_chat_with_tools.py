"""Integration tests for chat flows with tools.

These tests focus on the persisted message ordering for tool-call flows.

Expected canonical ordering:
1. user
2. assistant (with tool_calls)
3. tool
4. assistant (final answer)
"""

import json

import pytest
from httpx import AsyncClient

from mochi_server.tools.config import ToolExecutionPolicy


@pytest.fixture(autouse=True)
def sample_tools(test_settings):
    """Create sample tools in the test tools directory for chat tool tests."""
    tools_dir = test_settings.resolved_tools_dir
    tools_dir.mkdir(parents=True, exist_ok=True)

    math_dir = tools_dir / "math_tools"
    math_dir.mkdir(exist_ok=True)
    (math_dir / "__init__.py").write_text(
        '''
__all__ = ["multiply_numbers"]

def multiply_numbers(a: int, b: int) -> str:
    """Multiply two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The product of the two numbers as a string
    """
    return str(a * b)
'''
    )

    utilities_dir = tools_dir / "utilities"
    utilities_dir.mkdir(exist_ok=True)
    (utilities_dir / "__init__.py").write_text(
        '''
__all__ = ["flip_coin"]

def flip_coin() -> str:
    """Flip a coin.

    Returns:
        The coin flip result
    """
    return "heads"
'''
    )

    yield


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE response text into structured events."""
    events = []
    normalized_text = response_text.replace("\r\n", "\n")
    chunks = normalized_text.strip().split("\n\n")

    for chunk in chunks:
        if not chunk.strip():
            continue

        event_type = None
        event_data = None

        for line in chunk.split("\n"):
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                event_data = line.split(":", 1)[1].strip()

        if event_type and event_data:
            events.append({"event": event_type, "data": json.loads(event_data)})

    return events


class TestChatWithTools:
    """Integration tests for tool-enabled chat flows."""

    @pytest.mark.asyncio
    async def test_non_streaming_persists_correct_tool_message_order(
        self,
        async_client: AsyncClient,
        mock_ollama_client,
    ):
        """Non-streaming chat should persist assistant->tool->assistant ordering."""
        # Create a session with tools enabled
        create_response = await async_client.post(
            "/api/v1/sessions",
            json={
                "model": "llama3.2:latest",
                "tool_settings": {
                    "tools": ["multiply_numbers"],
                    "execution_policy": "never_confirm",
                },
            },
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        call_count = 0

        async def mock_chat_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First assistant turn requests a tool
                yield {
                    "model": "llama3.2:latest",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "multiply_numbers",
                                    "arguments": {"a": 12, "b": 5},
                                }
                            }
                        ],
                    },
                    "done": True,
                    "eval_count": 8,
                    "prompt_eval_count": 40,
                }
            elif call_count == 2:
                # Continuation after tool result
                yield {
                    "model": "llama3.2:latest",
                    "message": {
                        "role": "assistant",
                        "content": "12 × 5 = 60",
                    },
                    "done": True,
                    "eval_count": 12,
                    "prompt_eval_count": 80,
                }
            else:
                raise AssertionError("Unexpected extra Ollama call")

        mock_ollama_client.chat_stream = mock_chat_stream

        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "What is 12 times 5?"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "12 × 5 = 60"
        assert data["tool_calls_executed"] == [
            {
                "name": "multiply_numbers",
                "arguments": {"a": 12, "b": 5},
                "success": True,
            }
        ]

        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        assert len(messages) == 4

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is 12 times 5?"

        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == ""
        assert messages[1]["tool_calls"] == [
            {
                "function": {
                    "name": "multiply_numbers",
                    "arguments": {"a": 12, "b": 5},
                }
            }
        ]

        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_name"] == "multiply_numbers"
        assert messages[2]["content"] == "60"

        assert messages[3]["role"] == "assistant"
        assert messages[3]["content"] == "12 × 5 = 60"
        assert messages[3]["tool_calls"] is None

    @pytest.mark.asyncio
    async def test_streaming_persists_correct_tool_message_order(
        self,
        async_client: AsyncClient,
        mock_ollama_client,
    ):
        """Streaming chat should persist assistant->tool->assistant ordering."""
        create_response = await async_client.post(
            "/api/v1/sessions",
            json={
                "model": "llama3.2:latest",
                "tool_settings": {
                    "tools": ["flip_coin"],
                    "execution_policy": "never_confirm",
                },
            },
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        call_count = 0

        async def mock_chat_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                yield {
                    "model": "llama3.2:latest",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "flip_coin",
                                    "arguments": {},
                                }
                            }
                        ],
                    },
                    "done": True,
                    "eval_count": 5,
                    "prompt_eval_count": 25,
                }
            elif call_count == 2:
                yield {
                    "model": "llama3.2:latest",
                    "message": {
                        "role": "assistant",
                        "content": "The result is heads.",
                    },
                    "done": True,
                    "eval_count": 9,
                    "prompt_eval_count": 55,
                }
            else:
                raise AssertionError("Unexpected extra Ollama call")

        mock_ollama_client.chat_stream = mock_chat_stream

        response = await async_client.post(
            f"/api/v1/chat/{session_id}/stream",
            json={"message": "Flip a coin please"},
        )
        assert response.status_code == 200

        events = _parse_sse_events(response.text)

        event_types = [event["event"] for event in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "tool_continuation_start" in event_types
        assert "message_complete" in event_types
        assert "done" in event_types

        tool_call_events = [event for event in events if event["event"] == "tool_call"]
        assert len(tool_call_events) == 1
        assert tool_call_events[0]["data"]["tool_name"] == "flip_coin"
        assert tool_call_events[0]["data"]["arguments"] == {}

        tool_result_events = [
            event for event in events if event["event"] == "tool_result"
        ]
        assert len(tool_result_events) == 1
        assert tool_result_events[0]["data"]["tool_name"] == "flip_coin"
        assert tool_result_events[0]["data"]["result"] in {"heads", "tails"}

        messages_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/messages"
        )
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]

        assert len(messages) == 4

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Flip a coin please"

        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == ""
        assert messages[1]["tool_calls"] == [
            {
                "function": {
                    "name": "flip_coin",
                    "arguments": {},
                }
            }
        ]

        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_name"] == "flip_coin"
        assert messages[2]["content"] in {"heads", "tails"}

        assert messages[3]["role"] == "assistant"
        assert messages[3]["content"] == "The result is heads."
        assert messages[3]["tool_calls"] is None

    @pytest.mark.asyncio
    async def test_non_streaming_rejects_always_confirm_tool_execution(
        self,
        async_client: AsyncClient,
        mock_ollama_client,
    ):
        """Non-streaming tool confirmation should require the streaming endpoint."""
        create_response = await async_client.post(
            "/api/v1/sessions",
            json={
                "model": "llama3.2:latest",
                "tool_settings": {
                    "tools": ["multiply_numbers"],
                    "execution_policy": "always_confirm",
                },
            },
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        async def mock_chat_stream(*args, **kwargs):
            yield {
                "model": "llama3.2:latest",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "multiply_numbers",
                                "arguments": {"a": 12, "b": 5},
                            }
                        }
                    ],
                },
                "done": True,
                "eval_count": 8,
                "prompt_eval_count": 40,
            }

        mock_ollama_client.chat_stream = mock_chat_stream

        response = await async_client.post(
            f"/api/v1/chat/{session_id}",
            json={"message": "What is 12 times 5?"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == (
            "tool_confirmation_requires_streaming"
        )

    def test_policy_always_confirm(self):
        """Verify always_confirm policy value."""
        policy = ToolExecutionPolicy.ALWAYS_CONFIRM
        assert policy.value == "always_confirm"

    def test_policy_never_confirm(self):
        """Verify never_confirm policy value."""
        policy = ToolExecutionPolicy.NEVER_CONFIRM
        assert policy.value == "never_confirm"
