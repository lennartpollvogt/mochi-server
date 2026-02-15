"""ChatSession class for managing individual chat sessions.

This module provides the ChatSession class which handles:
- Loading and saving session data to JSON files
- Adding messages to the conversation history
- Editing messages and truncating history
- Managing session metadata
- Session format versioning
"""

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mochi_server.sessions.types import (
    AgentSettings,
    AssistantMessage,
    ContextWindowConfig,
    ConversationSummary,
    Message,
    SessionMetadata,
    SystemMessage,
    ToolMessage,
    ToolSettings,
    UserMessage,
)

logger = logging.getLogger(__name__)


def _message_from_dict(data: dict[str, Any]) -> Message:
    """Convert a dictionary to the appropriate Message type.

    Args:
        data: Message data as a dictionary

    Returns:
        Appropriate Message dataclass instance

    Raises:
        ValueError: If role is unknown
    """
    role = data.get("role")

    if role == "user":
        return UserMessage(**data)
    elif role == "system":
        return SystemMessage(**data)
    elif role == "assistant":
        return AssistantMessage(**data)
    elif role == "tool":
        return ToolMessage(**data)
    else:
        raise ValueError(f"Unknown message role: {role}")


class ChatSession:
    """Represents a single chat session with message history and metadata.

    A session is persisted as a JSON file with the following structure:
    {
        "metadata": {...},
        "messages": [...]
    }
    """

    def __init__(
        self,
        session_id: str,
        model: str,
        messages: list[Message] | None = None,
        metadata: SessionMetadata | None = None,
    ):
        """Initialize a ChatSession.

        Args:
            session_id: Unique session identifier (10-char hex)
            model: The LLM model name for this session
            messages: Initial message history (default: empty)
            metadata: Session metadata (default: auto-generated)
        """
        self.session_id = session_id
        self.model = model
        self.messages: list[Message] = messages or []

        # Initialize metadata if not provided
        if metadata is None:
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self.metadata = SessionMetadata(
                session_id=session_id,
                model=model,
                created_at=now,
                updated_at=now,
                message_count=len(self.messages),
            )
        else:
            self.metadata = metadata

    def add_message(self, message: Message) -> None:
        """Add a message to the session history.

        Updates the message_count in metadata and the updated_at timestamp.

        Args:
            message: The message to add
        """
        self.messages.append(message)
        self.metadata.message_count = len(self.messages)
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def edit_message(self, index: int, content: str) -> None:
        """Edit a message and truncate all messages after it.

        This is used when a user wants to edit a previous message and
        regenerate the conversation from that point.

        Args:
            index: The index of the message to edit (0-based)
            content: The new content for the message

        Raises:
            IndexError: If index is out of range
            ValueError: If trying to edit a non-user message
        """
        if index < 0 or index >= len(self.messages):
            raise IndexError(
                f"Message index {index} out of range (0-{len(self.messages) - 1})"
            )

        message = self.messages[index]
        if not isinstance(message, UserMessage):
            raise ValueError("Can only edit user messages")

        # Update the message content
        message.content = content
        message.timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Truncate all messages after this one
        self.messages = self.messages[: index + 1]

        # Update metadata
        self.metadata.message_count = len(self.messages)
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def update_model(self, model: str) -> None:
        """Update the model used by this session.

        Args:
            model: The new model name
        """
        self.model = model
        self.metadata.model = model
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def update_tool_settings(self, tool_settings: ToolSettings) -> None:
        """Update tool settings for this session.

        Args:
            tool_settings: New tool settings
        """
        self.metadata.tool_settings = tool_settings
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def update_agent_settings(self, agent_settings: AgentSettings) -> None:
        """Update agent settings for this session.

        Args:
            agent_settings: New agent settings
        """
        self.metadata.agent_settings = agent_settings
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def has_system_prompt(self) -> bool:
        """Check if the session has a system prompt.

        Returns:
            True if the first message is a system message, False otherwise
        """
        return len(self.messages) > 0 and isinstance(self.messages[0], SystemMessage)

    def set_system_prompt(self, content: str, source_file: str | None = None) -> None:
        """Set or update the system prompt for this session.

        If a system prompt already exists (at index 0), it will be replaced.
        If no system prompt exists, a new one will be added at index 0.

        Note: This does NOT truncate the conversation history.

        Args:
            content: The content of the system prompt
            source_file: Optional filename reference for tracking prompt source
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        system_message = SystemMessage(
            content=content,
            source_file=source_file,
            message_id=ChatSession.generate_session_id(),
            timestamp=now,
        )

        if self.has_system_prompt():
            # Replace existing system prompt at index 0
            self.messages[0] = system_message
            logger.debug(f"Replaced system prompt in session {self.session_id}")
        else:
            # Insert new system prompt at the beginning
            self.messages.insert(0, system_message)
            logger.debug(f"Added system prompt to session {self.session_id}")

        # Update metadata
        self.metadata.message_count = len(self.messages)
        self.metadata.updated_at = now

    def remove_system_prompt(self) -> None:
        """Remove the system prompt from this session.

        If a system prompt exists (at index 0), it will be deleted and
        subsequent messages will shift up.

        Raises:
            ValueError: If no system prompt exists to remove
        """
        if not self.has_system_prompt():
            raise ValueError("No system prompt to remove")

        # Remove the system message at index 0
        self.messages.pop(0)
        logger.debug(f"Removed system prompt from session {self.session_id}")

        # Update metadata
        self.metadata.message_count = len(self.messages)
        self.metadata.updated_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert session to a dictionary for JSON serialization.

        Returns:
            Dictionary representation of the session
        """
        # Convert metadata
        metadata_dict = {
            "session_id": self.metadata.session_id,
            "model": self.metadata.model,
            "created_at": self.metadata.created_at,
            "updated_at": self.metadata.updated_at,
            "message_count": self.metadata.message_count,
            "summary": (
                {
                    "summary": self.metadata.summary.summary,
                    "topics": self.metadata.summary.topics,
                }
                if self.metadata.summary
                else None
            ),
            "summary_model": self.metadata.summary_model,
            "format_version": self.metadata.format_version,
            "tool_settings": asdict(self.metadata.tool_settings),
            "agent_settings": asdict(self.metadata.agent_settings),
            "context_window_config": asdict(self.metadata.context_window_config),
        }

        # Convert messages
        messages_list = [asdict(msg) for msg in self.messages]

        return {"metadata": metadata_dict, "messages": messages_list}

    def save(self, sessions_dir: Path) -> None:
        """Save the session to a JSON file.

        Args:
            sessions_dir: Directory where session files are stored
        """
        sessions_dir.mkdir(parents=True, exist_ok=True)
        file_path = sessions_dir / f"{self.session_id}.json"

        data = self.to_dict()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved session {self.session_id} to {file_path}")

    @classmethod
    def load(cls, session_id: str, sessions_dir: Path) -> "ChatSession":
        """Load a session from a JSON file.

        Handles format migration automatically if the file is an older version.

        Args:
            session_id: The session ID to load
            sessions_dir: Directory where session files are stored

        Returns:
            Loaded ChatSession instance

        Raises:
            FileNotFoundError: If session file doesn't exist
            ValueError: If session data is invalid
        """
        file_path = sessions_dir / f"{session_id}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse metadata
        metadata_dict = data["metadata"]
        summary_dict = metadata_dict.get("summary")

        metadata = SessionMetadata(
            session_id=metadata_dict["session_id"],
            model=metadata_dict["model"],
            created_at=metadata_dict["created_at"],
            updated_at=metadata_dict["updated_at"],
            message_count=metadata_dict.get("message_count", 0),
            summary=(
                ConversationSummary(
                    summary=summary_dict.get("summary", ""),
                    topics=summary_dict.get("topics", []),
                )
                if summary_dict
                else None
            ),
            summary_model=metadata_dict.get("summary_model"),
            format_version=metadata_dict.get("format_version", "1.3"),
            tool_settings=ToolSettings(**metadata_dict.get("tool_settings", {})),
            agent_settings=AgentSettings(**metadata_dict.get("agent_settings", {})),
            context_window_config=ContextWindowConfig(
                **metadata_dict.get("context_window_config", {})
            ),
        )

        # Parse messages
        messages = [
            _message_from_dict(msg_dict) for msg_dict in data.get("messages", [])
        ]

        return cls(
            session_id=session_id,
            model=metadata.model,
            messages=messages,
            metadata=metadata,
        )

    @staticmethod
    def generate_session_id() -> str:
        """Generate a new unique session ID.

        Returns:
            10-character hexadecimal string
        """
        return uuid.uuid4().hex[:10]

    def get_preview(self, max_length: int = 100) -> str:
        """Get a preview of the session (first user message).

        Args:
            max_length: Maximum length of the preview

        Returns:
            Preview string, truncated if necessary
        """
        for message in self.messages:
            if isinstance(message, UserMessage):
                content = message.content
                if len(content) > max_length:
                    return content[: max_length - 3] + "..."
                return content
        return ""
