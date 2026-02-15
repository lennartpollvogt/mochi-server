"""SessionManager for CRUD operations on chat sessions.

This module provides the SessionManager class which handles:
- Creating new sessions with model validation
- Listing sessions with sorting and filtering
- Retrieving session details
- Updating session metadata
- Deleting sessions
"""

import logging
from datetime import datetime
from pathlib import Path

from mochi_server.ollama.client import OllamaClient
from mochi_server.sessions.session import ChatSession
from mochi_server.sessions.types import (
    AgentSettings,
    Message,
    SessionCreationOptions,
    SystemMessage,
    ToolSettings,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions with CRUD operations.

    The SessionManager operates on a directory of JSON session files
    and provides high-level operations for session management.
    """

    def __init__(self, sessions_dir: Path, ollama_client: OllamaClient | None = None):
        """Initialize the SessionManager.

        Args:
            sessions_dir: Directory where session JSON files are stored
            ollama_client: Optional Ollama client for model validation
        """
        self.sessions_dir = sessions_dir
        self.ollama_client = ollama_client
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    async def create_session(self, options: SessionCreationOptions) -> ChatSession:
        """Create a new chat session.

        Args:
            options: Session creation options including model, prompts, settings

        Returns:
            The newly created ChatSession

        Raises:
            ValueError: If the model doesn't exist (when ollama_client is provided)
        """
        # Validate model exists if we have an Ollama client
        if self.ollama_client:
            model_info = await self.ollama_client.get_model_info(options.model)
            if model_info is None:
                raise ValueError(f"Model '{options.model}' not found")

        # Generate new session ID
        session_id = ChatSession.generate_session_id()

        # Create the session
        session = ChatSession(session_id=session_id, model=options.model)

        # Apply tool settings if provided
        if options.tool_settings:
            session.update_tool_settings(options.tool_settings)

        # Apply agent settings if provided
        if options.agent_settings:
            session.update_agent_settings(options.agent_settings)

        # Add system message if provided
        if options.system_prompt:
            now = datetime.utcnow().isoformat() + "Z"
            system_message = SystemMessage(
                content=options.system_prompt,
                source_file=options.system_prompt_source_file,
                message_id=ChatSession.generate_session_id(),
                timestamp=now,
            )
            session.add_message(system_message)

        # Save to disk
        session.save(self.sessions_dir)

        logger.info(f"Created new session {session_id} with model {options.model}")
        return session

    def list_sessions(self) -> list[ChatSession]:
        """List all sessions, sorted by updated_at descending.

        Returns:
            List of ChatSession objects, newest first
        """
        sessions: list[ChatSession] = []

        # Scan directory for .json files
        for file_path in self.sessions_dir.glob("*.json"):
            session_id = file_path.stem
            try:
                session = ChatSession.load(session_id, self.sessions_dir)
                sessions.append(session)
            except Exception as e:
                logger.warning(f"Failed to load session {session_id}: {e}")
                continue

        # Sort by updated_at descending (newest first)
        sessions.sort(
            key=lambda s: s.metadata.updated_at,
            reverse=True,
        )

        logger.debug(f"Listed {len(sessions)} sessions")
        return sessions

    def get_session(self, session_id: str) -> ChatSession:
        """Get a specific session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            The ChatSession object

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        session = ChatSession.load(session_id, self.sessions_dir)
        logger.debug(f"Retrieved session {session_id}")
        return session

    def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: The session ID to delete

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        file_path = self.sessions_dir / f"{session_id}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        file_path.unlink()
        logger.info(f"Deleted session {session_id}")

    async def update_session(
        self,
        session_id: str,
        model: str | None = None,
        tool_settings: ToolSettings | None = None,
        agent_settings: AgentSettings | None = None,
    ) -> ChatSession:
        """Update session metadata.

        Args:
            session_id: The session ID to update
            model: Optional new model name
            tool_settings: Optional new tool settings
            agent_settings: Optional new agent settings

        Returns:
            The updated ChatSession

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If new model doesn't exist (when ollama_client is provided)
        """
        # Load the session
        session = self.get_session(session_id)

        # Update model if provided
        if model is not None:
            # Validate model exists if we have an Ollama client
            if self.ollama_client:
                model_info = await self.ollama_client.get_model_info(model)
                if model_info is None:
                    raise ValueError(f"Model '{model}' not found")

            session.update_model(model)

        # Update tool settings if provided
        if tool_settings is not None:
            session.update_tool_settings(tool_settings)

        # Update agent settings if provided
        if agent_settings is not None:
            session.update_agent_settings(agent_settings)

        # Save changes
        session.save(self.sessions_dir)

        logger.info(f"Updated session {session_id}")
        return session

    def get_messages(self, session_id: str) -> list[Message]:
        """Get all messages from a session.

        Args:
            session_id: The session ID

        Returns:
            List of messages in the session

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        session = self.get_session(session_id)
        return session.messages
