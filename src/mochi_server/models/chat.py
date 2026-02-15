"""Pydantic models for chat API requests and responses.

This module defines the request and response schemas for the chat endpoints,
including both streaming and non-streaming chat interactions.
"""

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request body for chat endpoints.

    Used by both POST /api/v1/chat/{session_id} (non-streaming)
    and POST /api/v1/chat/{session_id}/stream (streaming).
    """

    message: str | None = Field(
        default=None,
        description="The user message to send. If null, re-generates from the last user message in session history.",
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
