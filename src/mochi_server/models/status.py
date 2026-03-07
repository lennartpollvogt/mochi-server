"""Pydantic models for session status endpoint.

This module defines the response schemas for the session status endpoint,
which provides full session state information including context window
management details.
"""

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummaryStatus(BaseModel):
    """Summary information for a session."""

    summary: str = Field(
        default="",
        description="Summary of the conversation",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="List of topics discussed",
    )

    model_config = ConfigDict(from_attributes=True)


class ContextWindowStatus(BaseModel):
    """Context window configuration and status for a session.

    This model provides detailed information about the context window
    management settings and current state.
    """

    dynamic_enabled: bool = Field(
        description="Whether dynamic context window sizing is enabled",
    )
    current_window: int = Field(
        description="Current context window size in tokens",
    )
    model_max_context: int | None = Field(
        default=None,
        description="Model's maximum context length in tokens",
    )
    last_adjustment_reason: str = Field(
        description="Reason for the last context window adjustment",
    )
    manual_override: bool = Field(
        description="Whether the context window was manually set by the user",
    )

    model_config = ConfigDict(from_attributes=True)


class SessionStatusResponse(BaseModel):
    """Response body for GET /api/v1/sessions/{session_id}/status.

    This endpoint provides full session state information including
    context window details, active tools, agents, system prompt, and summary.
    """

    session_id: str = Field(
        description="Unique session identifier",
    )
    model: str = Field(
        description="The LLM model used by this session",
    )
    message_count: int = Field(
        description="Number of messages in the conversation",
    )
    context_window: ContextWindowStatus = Field(
        description="Context window configuration and status",
    )
    tools_enabled: bool = Field(
        description="Whether tools are enabled for this session",
    )
    active_tools: list[str] = Field(
        default_factory=list,
        description="List of active tool names",
    )
    execution_policy: str = Field(
        description="Tool execution policy (always_confirm, never_confirm, auto)",
    )
    agents_enabled: bool = Field(
        description="Whether agents are enabled for this session",
    )
    enabled_agents: list[str] = Field(
        default_factory=list,
        description="List of enabled agent names",
    )
    system_prompt_file: str | None = Field(
        default=None,
        description="Source file for the system prompt (if any)",
    )
    summary: ConversationSummaryStatus | None = Field(
        default=None,
        description="Conversation summary (if available)",
    )
    summary_model: str | None = Field(
        default=None,
        description="Model used for summarization (if available)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "a1b2c3d4e5",
                "model": "qwen3:14b",
                "message_count": 12,
                "context_window": {
                    "dynamic_enabled": True,
                    "current_window": 8192,
                    "model_max_context": 40960,
                    "last_adjustment_reason": "usage_threshold",
                    "manual_override": False,
                },
                "tools_enabled": True,
                "active_tools": ["add_numbers", "get_current_time"],
                "execution_policy": "always_confirm",
                "agents_enabled": True,
                "enabled_agents": ["coder"],
                "system_prompt_file": "using_agents.md",
                "summary": {
                    "summary": "Discussion about Python patterns...",
                    "topics": ["python", "design patterns"],
                },
                "summary_model": "qwen3:14b",
            }
        }
    )
