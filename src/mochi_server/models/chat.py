"""Pydantic models for chat API requests and responses.

This module defines the request and response schemas for the chat endpoints,
including both streaming and non-streaming chat interactions.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request body for chat endpoints.

    Used by both POST /api/v1/chat/{session_id} (non-streaming)
    and POST /api/v1/chat/{session_id}/stream (streaming).

    Message Behavior:
    - message="some text" → Adds a new user message and generates response
    - message=null (or omitted) → Continues from existing history without adding user message
      - If last message is user → Regenerates the assistant response
      - If last message is assistant → Continues the conversation (useful for agent loops)
    """

    message: str | None = Field(
        default=None,
        description=(
            "The user message to send. If null or omitted, continues from the existing "
            "message history without adding a new user message. This allows regenerating "
            "responses or continuing multi-turn agent loops where the LLM builds upon its "
            "own previous output."
        ),
    )
    think: bool = Field(
        default=False,
        description="Whether to request thinking/reasoning from the model (if supported).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What is the capital of France?",
                    "think": False,
                },
                {
                    "message": None,
                    "think": False,
                    "description": "Regenerate or continue from existing history",
                },
            ]
        }
    )


class MessageResponse(BaseModel):
    """Response schema for a single message in chat response."""

    role: str = Field(description="Message role (assistant)")
    content: str = Field(description="Message content")
    model: str = Field(description="Model that generated this message")
    message_id: str = Field(description="Unique message identifier")
    timestamp: str = Field(description="ISO 8601 timestamp")
    eval_count: int | None = Field(
        default=None, description="Number of tokens generated"
    )
    prompt_eval_count: int | None = Field(
        default=None, description="Number of tokens in the prompt"
    )
    tool_calls: list[dict] | None = Field(
        default=None, description="Tool calls made by the assistant (if any)"
    )

    model_config = ConfigDict(from_attributes=True)


class ContextWindowInfo(BaseModel):
    """Information about the context window used in the chat."""

    current_window: int = Field(description="Current context window size in tokens")
    usage_tokens: int = Field(
        default=0, description="Number of tokens used in this request"
    )
    reason: str = Field(
        default="initial_setup",
        description="Reason for the current context window size",
    )


class ChatResponse(BaseModel):
    """Response body for non-streaming chat endpoint.

    This is returned by POST /api/v1/chat/{session_id} after the full
    response has been collected from the streaming Ollama API.
    """

    session_id: str = Field(description="Session identifier")
    message: MessageResponse = Field(description="The assistant's response message")
    tool_calls_executed: list[dict] = Field(
        default_factory=list,
        description="List of tools that were executed during this response (empty in Phase 3)",
    )
    context_window: ContextWindowInfo = Field(
        description="Information about the context window"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "a1b2c3d4e5",
                "message": {
                    "role": "assistant",
                    "content": "The capital of France is Paris.",
                    "model": "llama3.2:latest",
                    "message_id": "f1e2d3c4b5",
                    "timestamp": "2025-01-15T10:35:00.000000Z",
                    "eval_count": 45,
                    "prompt_eval_count": 120,
                    "tool_calls": None,
                },
                "tool_calls_executed": [],
                "context_window": {
                    "current_window": 8192,
                    "usage_tokens": 165,
                    "reason": "initial_setup",
                },
            }
        }
    )


# ============================================================================
# SSE Event Payload Models (Phase 4: Streaming Chat)
# ============================================================================


class ContentDeltaEvent(BaseModel):
    """SSE event payload for content deltas during streaming."""

    content: str = Field(description="Text chunk from the LLM")
    role: str = Field(default="assistant", description="Message role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Hello",
                "role": "assistant",
            }
        }
    )


class ThinkingDeltaEvent(BaseModel):
    """SSE event payload for thinking/reasoning chunks."""

    content: str = Field(description="Thinking content chunk")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Let me consider...",
            }
        }
    )


class MessageCompleteEvent(BaseModel):
    """SSE event payload when message is complete with full metadata."""

    message_id: str = Field(description="Unique message identifier")
    model: str = Field(description="Model that generated the message")
    eval_count: int | None = Field(
        default=None, description="Number of tokens generated"
    )
    prompt_eval_count: int | None = Field(
        default=None, description="Number of tokens in the prompt"
    )
    context_window: ContextWindowInfo = Field(description="Context window information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_id": "a1b2c3d4e5",
                "model": "llama3.2:latest",
                "eval_count": 45,
                "prompt_eval_count": 120,
                "context_window": {
                    "current_window": 8192,
                    "usage_tokens": 165,
                    "reason": "initial_setup",
                },
            }
        }
    )


class ErrorEvent(BaseModel):
    """SSE event payload for errors during streaming."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error details"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "ollama_error",
                "message": "Failed to generate response",
                "details": {"session_id": "abc123"},
            }
        }
    )


class DoneEvent(BaseModel):
    """SSE event payload when stream is complete."""

    session_id: str = Field(description="Session identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "a1b2c3d4e5",
            }
        }
    )


# ============================================================================
# SSE Event Payload Models (Phase 7: Tool System)
# ============================================================================


class ToolCallEvent(BaseModel):
    """SSE event payload when LLM requests a tool execution (auto-execute policy)."""

    tool_name: str = Field(description="Name of the tool to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool",
    )
    tool_call_id: str = Field(
        description="Unique identifier for this tool call",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tool_name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
                "tool_call_id": "call_abc123",
            }
        }
    )


class ToolCallConfirmationRequiredEvent(BaseModel):
    """SSE event payload when LLM requests a tool (always_confirm policy).

    The client must respond via POST /api/v1/chat/{session_id}/confirm-tool
    to approve or deny the tool execution.
    """

    confirmation_id: str = Field(
        description="Unique ID to use in confirm-tool endpoint",
    )
    tool_name: str = Field(description="Name of the tool to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confirmation_id": "conf_abc123",
                "tool_name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
            }
        }
    )


class ToolResultEvent(BaseModel):
    """SSE event payload after tool execution completes."""

    tool_name: str = Field(description="Name of the tool that was executed")
    result: str = Field(description="Result from the tool execution")
    success: bool = Field(description="Whether the tool executed successfully")
    error: str | None = Field(
        default=None,
        description="Error message if execution failed",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tool_name": "add_numbers",
                "result": "5",
                "success": True,
                "error": None,
            }
        }
    )


class ToolContinuationStartEvent(BaseModel):
    """SSE event payload before sending tool results back to LLM for continuation."""

    tool_count: int = Field(
        description="Number of tool results being sent to the LLM",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tool_count": 2,
            }
        }
    )
