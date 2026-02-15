"""Unit tests for SessionManager CRUD operations.

Tests session manager's ability to create, list, retrieve, update,
and delete sessions with proper model validation.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from mochi_server.ollama import ModelInfo
from mochi_server.sessions import (
    AgentSettings,
    ChatSession,
    SessionCreationOptions,
    SessionManager,
    ToolSettings,
    UserMessage,
)


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create a temporary sessions directory."""
    return tmp_path / "sessions"


@pytest.fixture
def mock_ollama_client():
    """Create a mock OllamaClient."""
    mock_client = AsyncMock()

    # Mock get_model_info to return a valid model
    mock_client.get_model_info.return_value = ModelInfo(
        name="llama3:8b",
        size_mb=4445.3,
        format="gguf",
        family="llama",
        parameter_size="8.0B",
        quantization_level="Q4_0",
        capabilities=["completion"],
        context_length=8192,
    )

    return mock_client


@pytest.mark.asyncio
async def test_create_session(sessions_dir: Path, mock_ollama_client):
    """Test creating a new session."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    options = SessionCreationOptions(model="llama3:8b")
    session = await manager.create_session(options)

    assert session.session_id is not None
    assert len(session.session_id) == 10
    assert session.model == "llama3:8b"
    assert session.metadata.message_count == 0
    assert session.metadata.format_version == "1.3"

    # Verify it was saved to disk
    session_file = sessions_dir / f"{session.session_id}.json"
    assert session_file.exists()


@pytest.mark.asyncio
async def test_create_session_validates_model(sessions_dir: Path, mock_ollama_client):
    """Test that create_session validates model exists."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    # Mock get_model_info to return None (model not found)
    mock_ollama_client.get_model_info.return_value = None

    options = SessionCreationOptions(model="nonexistent:model")

    with pytest.raises(ValueError, match="Model 'nonexistent:model' not found"):
        await manager.create_session(options)


@pytest.mark.asyncio
async def test_create_session_without_ollama_client(sessions_dir: Path):
    """Test creating session without Ollama client (no validation)."""
    manager = SessionManager(sessions_dir, ollama_client=None)

    options = SessionCreationOptions(model="any:model")
    session = await manager.create_session(options)

    assert session.model == "any:model"
    assert session.session_id is not None


@pytest.mark.asyncio
async def test_create_session_with_system_prompt(
    sessions_dir: Path, mock_ollama_client
):
    """Test creating a session with a system prompt."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    options = SessionCreationOptions(
        model="llama3:8b",
        system_prompt="You are a helpful assistant",
        system_prompt_source_file="helpful.md",
    )
    session = await manager.create_session(options)

    assert session.metadata.message_count == 1
    assert len(session.messages) == 1
    assert session.messages[0].role == "system"
    assert session.messages[0].content == "You are a helpful assistant"
    # Type assertion for accessing SystemMessage-specific attribute
    from mochi_server.sessions.types import SystemMessage

    assert isinstance(session.messages[0], SystemMessage)
    assert session.messages[0].source_file == "helpful.md"


@pytest.mark.asyncio
async def test_create_session_with_tool_settings(
    sessions_dir: Path, mock_ollama_client
):
    """Test creating a session with tool settings."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    tool_settings = ToolSettings(
        tools=["tool1", "tool2"],
        tool_group="math",
        execution_policy="never_confirm",
    )
    options = SessionCreationOptions(model="llama3:8b", tool_settings=tool_settings)
    session = await manager.create_session(options)

    assert session.metadata.tool_settings.tools == ["tool1", "tool2"]
    assert session.metadata.tool_settings.tool_group == "math"
    assert session.metadata.tool_settings.execution_policy == "never_confirm"


@pytest.mark.asyncio
async def test_create_session_with_agent_settings(
    sessions_dir: Path, mock_ollama_client
):
    """Test creating a session with agent settings."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    agent_settings = AgentSettings(enabled_agents=["coder", "researcher"])
    options = SessionCreationOptions(model="llama3:8b", agent_settings=agent_settings)
    session = await manager.create_session(options)

    assert session.metadata.agent_settings.enabled_agents == ["coder", "researcher"]


def test_list_sessions_empty(sessions_dir: Path):
    """Test listing sessions when directory is empty."""
    manager = SessionManager(sessions_dir)

    sessions = manager.list_sessions()

    assert sessions == []


@pytest.mark.asyncio
async def test_list_sessions(sessions_dir: Path, mock_ollama_client):
    """Test listing multiple sessions."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    # Create multiple sessions
    options1 = SessionCreationOptions(model="llama3:8b")
    session1 = await manager.create_session(options1)

    options2 = SessionCreationOptions(model="qwen3:14b")
    session2 = await manager.create_session(options2)

    options3 = SessionCreationOptions(model="llama3:8b")
    session3 = await manager.create_session(options3)

    # List them
    sessions = manager.list_sessions()

    assert len(sessions) == 3
    session_ids = [s.session_id for s in sessions]
    assert session1.session_id in session_ids
    assert session2.session_id in session_ids
    assert session3.session_id in session_ids


@pytest.mark.asyncio
async def test_list_sessions_sorted_by_updated_at(
    sessions_dir: Path, mock_ollama_client
):
    """Test that sessions are sorted by updated_at descending (newest first)."""
    manager = SessionManager(sessions_dir, mock_ollama_client)

    # Create sessions with different update times
    options = SessionCreationOptions(model="llama3:8b")
    session1 = await manager.create_session(options)
    session1.metadata.updated_at = "2024-01-01T10:00:00Z"
    session1.save(sessions_dir)

    session2 = await manager.create_session(options)
    session2.metadata.updated_at = "2024-01-01T12:00:00Z"
    session2.save(sessions_dir)

    session3 = await manager.create_session(options)
    session3.metadata.updated_at = "2024-01-01T11:00:00Z"
    session3.save(sessions_dir)

    # List sessions
    sessions = manager.list_sessions()

    # Should be sorted by updated_at descending
    assert sessions[0].session_id == session2.session_id  # 12:00
    assert sessions[1].session_id == session3.session_id  # 11:00
    assert sessions[2].session_id == session1.session_id  # 10:00


def test_get_session(sessions_dir: Path):
    """Test retrieving a specific session."""
    # Create a session manually
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    # Retrieve it via manager
    manager = SessionManager(sessions_dir)
    retrieved = manager.get_session("test123")

    assert retrieved.session_id == "test123"
    assert retrieved.model == "llama3:8b"


def test_get_session_not_found(sessions_dir: Path):
    """Test retrieving a nonexistent session raises FileNotFoundError."""
    manager = SessionManager(sessions_dir)

    with pytest.raises(FileNotFoundError):
        manager.get_session("nonexistent")


def test_delete_session(sessions_dir: Path):
    """Test deleting a session."""
    # Create a session
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    session_file = sessions_dir / "test123.json"
    assert session_file.exists()

    # Delete it
    manager = SessionManager(sessions_dir)
    manager.delete_session("test123")

    # Verify it's gone
    assert not session_file.exists()


def test_delete_session_not_found(sessions_dir: Path):
    """Test deleting a nonexistent session raises FileNotFoundError."""
    manager = SessionManager(sessions_dir)

    with pytest.raises(FileNotFoundError):
        manager.delete_session("nonexistent")


@pytest.mark.asyncio
async def test_update_session_model(sessions_dir: Path, mock_ollama_client):
    """Test updating a session's model."""
    # Create initial session
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    # Update model
    manager = SessionManager(sessions_dir, mock_ollama_client)
    mock_ollama_client.get_model_info.return_value = ModelInfo(
        name="qwen3:14b",
        size_mb=8629.1,
        format="gguf",
        family="qwen2",
        parameter_size="14.8B",
        quantization_level="Q4_K_M",
        capabilities=["completion"],
        context_length=32768,
    )

    updated = await manager.update_session("test123", model="qwen3:14b")

    assert updated.model == "qwen3:14b"
    assert updated.metadata.model == "qwen3:14b"

    # Verify changes were persisted
    loaded = ChatSession.load("test123", sessions_dir)
    assert loaded.model == "qwen3:14b"


@pytest.mark.asyncio
async def test_update_session_model_not_found(sessions_dir: Path, mock_ollama_client):
    """Test updating to a nonexistent model raises ValueError."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    manager = SessionManager(sessions_dir, mock_ollama_client)
    mock_ollama_client.get_model_info.return_value = None

    with pytest.raises(ValueError, match="Model 'invalid:model' not found"):
        await manager.update_session("test123", model="invalid:model")


@pytest.mark.asyncio
async def test_update_session_tool_settings(sessions_dir: Path):
    """Test updating session tool settings."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    manager = SessionManager(sessions_dir, ollama_client=None)
    new_settings = ToolSettings(
        tools=["new_tool"],
        tool_group="utilities",
        execution_policy="auto",
    )

    updated = await manager.update_session("test123", tool_settings=new_settings)

    assert updated.metadata.tool_settings.tools == ["new_tool"]
    assert updated.metadata.tool_settings.tool_group == "utilities"
    assert updated.metadata.tool_settings.execution_policy == "auto"


@pytest.mark.asyncio
async def test_update_session_agent_settings(sessions_dir: Path):
    """Test updating session agent settings."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.save(sessions_dir)

    manager = SessionManager(sessions_dir, ollama_client=None)
    new_settings = AgentSettings(enabled_agents=["agent1", "agent2"])

    updated = await manager.update_session("test123", agent_settings=new_settings)

    assert updated.metadata.agent_settings.enabled_agents == ["agent1", "agent2"]


@pytest.mark.asyncio
async def test_update_session_not_found(sessions_dir: Path):
    """Test updating a nonexistent session raises FileNotFoundError."""
    manager = SessionManager(sessions_dir, ollama_client=None)

    with pytest.raises(FileNotFoundError):
        await manager.update_session("nonexistent", model="llama3:8b")


def test_get_messages(sessions_dir: Path):
    """Test getting messages from a session."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(UserMessage(content="World", message_id="msg2", timestamp=now))
    session.save(sessions_dir)

    manager = SessionManager(sessions_dir)
    messages = manager.get_messages("test123")

    assert len(messages) == 2
    assert messages[0].content == "Hello"
    assert messages[1].content == "World"


def test_get_messages_not_found(sessions_dir: Path):
    """Test getting messages from nonexistent session raises FileNotFoundError."""
    manager = SessionManager(sessions_dir)

    with pytest.raises(FileNotFoundError):
        manager.get_messages("nonexistent")


def test_list_sessions_skips_invalid_files(sessions_dir: Path):
    """Test that list_sessions handles corrupted files gracefully."""
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Create a valid session
    session = ChatSession(session_id="valid", model="llama3:8b")
    session.save(sessions_dir)

    # Create an invalid JSON file
    invalid_file = sessions_dir / "invalid.json"
    invalid_file.write_text("not valid json")

    # List sessions should skip the invalid file and return the valid one
    manager = SessionManager(sessions_dir)
    sessions = manager.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].session_id == "valid"


@pytest.mark.asyncio
async def test_session_manager_creates_directory(tmp_path: Path, mock_ollama_client):
    """Test that SessionManager creates sessions directory if it doesn't exist."""
    sessions_dir = tmp_path / "new" / "sessions"
    assert not sessions_dir.exists()

    manager = SessionManager(sessions_dir, mock_ollama_client)

    # Should create the directory
    assert sessions_dir.exists()

    # Should be able to create a session
    options = SessionCreationOptions(model="llama3:8b")
    session = await manager.create_session(options)

    assert (sessions_dir / f"{session.session_id}.json").exists()
