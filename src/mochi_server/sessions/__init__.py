"""Session management for mochi-server.

This package provides session persistence, message history management,
and CRUD operations for chat sessions.
"""

from mochi_server.sessions.manager import SessionManager
from mochi_server.sessions.session import ChatSession
from mochi_server.sessions.types import (
    AgentSettings,
    AssistantMessage,
    ContextWindowConfig,
    ConversationSummary,
    Message,
    SessionCreationOptions,
    SessionMetadata,
    SystemMessage,
    ToolMessage,
    ToolSettings,
    UserMessage,
)

__all__ = [
    # Core classes
    "ChatSession",
    "SessionManager",
    # Message types
    "Message",
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "ToolMessage",
    # Configuration types
    "SessionMetadata",
    "SessionCreationOptions",
    "ToolSettings",
    "AgentSettings",
    "ContextWindowConfig",
    "ConversationSummary",
]
