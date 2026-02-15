"""Data types for session management.

This module defines the core data structures for chat sessions, messages,
and session configuration.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserMessage:
    """A message from the user."""

    role: str = "user"
    content: str = ""
    message_id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        """Validate role is always 'user'."""
        self.role = "user"


@dataclass
class SystemMessage:
    """A system prompt message."""

    role: str = "system"
    content: str = ""
    source_file: str | None = None
    message_id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        """Validate role is always 'system'."""
        self.role = "system"


@dataclass
class AssistantMessage:
    """A response from the LLM assistant."""

    role: str = "assistant"
    content: str = ""
    model: str = ""
    message_id: str = ""
    timestamp: str = ""
    eval_count: int | None = None
    prompt_eval_count: int | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        """Validate role is always 'assistant'."""
        self.role = "assistant"


@dataclass
class ToolMessage:
    """A tool execution result."""

    role: str = "tool"
    tool_name: str = ""
    content: str = ""
    message_id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        """Validate role is always 'tool'."""
        self.role = "tool"


# Union type for all message types
Message = UserMessage | SystemMessage | AssistantMessage | ToolMessage


@dataclass
class ConversationSummary:
    """Summary of a conversation session."""

    summary: str = ""
    topics: list[str] = field(default_factory=list)


@dataclass
class ToolSettings:
    """Configuration for tool execution in a session."""

    tools: list[str] = field(default_factory=list)
    tool_group: str | None = None
    execution_policy: str = "always_confirm"  # always_confirm | never_confirm | auto


@dataclass
class AgentSettings:
    """Configuration for agent execution in a session."""

    enabled_agents: list[str] = field(default_factory=list)


@dataclass
class ContextWindowConfig:
    """Context window management configuration."""

    dynamic_enabled: bool = True
    current_window: int = 8192
    last_adjustment: str = "initial_setup"
    adjustment_history: list[dict[str, Any]] = field(default_factory=list)
    manual_override: bool = False


@dataclass
class SessionMetadata:
    """Metadata for a chat session."""

    session_id: str
    model: str
    created_at: str
    updated_at: str
    message_count: int = 0
    summary: ConversationSummary | None = None
    summary_model: str | None = None
    format_version: str = "1.3"
    tool_settings: ToolSettings = field(default_factory=ToolSettings)
    agent_settings: AgentSettings = field(default_factory=AgentSettings)
    context_window_config: ContextWindowConfig = field(
        default_factory=ContextWindowConfig
    )


@dataclass
class SessionCreationOptions:
    """Options for creating a new session."""

    model: str
    system_prompt: str | None = None
    system_prompt_source_file: str | None = None
    tool_settings: ToolSettings | None = None
    agent_settings: AgentSettings | None = None
