"""Unit tests for ChatSession class.

Tests session creation, message management, editing, persistence,
and format compatibility.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from mochi_server.sessions import (
    AgentSettings,
    AssistantMessage,
    ChatSession,
    ConversationSummary,
    SessionMetadata,
    SystemMessage,
    ToolMessage,
    ToolSettings,
    UserMessage,
)


def test_create_new_session():
    """Test creating a new ChatSession."""
    session = ChatSession(session_id="test123", model="llama3:8b")

    assert session.session_id == "test123"
    assert session.model == "llama3:8b"
    assert len(session.messages) == 0
    assert session.metadata.session_id == "test123"
    assert session.metadata.model == "llama3:8b"
    assert session.metadata.message_count == 0
    assert session.metadata.format_version == "1.3"


def test_create_session_with_messages():
    """Test creating a session with initial messages."""
    now = datetime.utcnow().isoformat() + "Z"
    messages = [
        UserMessage(content="Hello", message_id="msg1", timestamp=now),
        AssistantMessage(
            content="Hi there!", model="llama3:8b", message_id="msg2", timestamp=now
        ),
    ]

    session = ChatSession(session_id="test123", model="llama3:8b", messages=messages)

    assert len(session.messages) == 2
    assert session.metadata.message_count == 2


def test_add_message():
    """Test adding a message to a session."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    message = UserMessage(content="Hello", message_id="msg1", timestamp=now)
    session.add_message(message)

    assert len(session.messages) == 1
    assert session.messages[0].content == "Hello"
    assert session.metadata.message_count == 1


def test_add_multiple_messages():
    """Test adding multiple messages updates count correctly."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(
        AssistantMessage(
            content="Hi!", model="llama3:8b", message_id="msg2", timestamp=now
        )
    )
    session.add_message(
        UserMessage(content="How are you?", message_id="msg3", timestamp=now)
    )

    assert len(session.messages) == 3
    assert session.metadata.message_count == 3


def test_edit_message():
    """Test editing a user message truncates history."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    # Add conversation
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(
        AssistantMessage(
            content="Hi!", model="llama3:8b", message_id="msg2", timestamp=now
        )
    )
    session.add_message(
        UserMessage(content="How are you?", message_id="msg3", timestamp=now)
    )
    session.add_message(
        AssistantMessage(
            content="I'm good!", model="llama3:8b", message_id="msg4", timestamp=now
        )
    )

    # Edit the first user message
    session.edit_message(0, "Hi there!")

    # Should keep only the edited message and truncate everything after
    assert len(session.messages) == 1
    assert session.messages[0].content == "Hi there!"
    assert session.metadata.message_count == 1


def test_edit_message_in_middle():
    """Test editing a message in the middle of conversation."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(
        AssistantMessage(
            content="Hi!", model="llama3:8b", message_id="msg2", timestamp=now
        )
    )
    session.add_message(
        UserMessage(content="How are you?", message_id="msg3", timestamp=now)
    )
    session.add_message(
        AssistantMessage(
            content="I'm good!", model="llama3:8b", message_id="msg4", timestamp=now
        )
    )

    # Edit the second user message (index 2)
    session.edit_message(2, "What's up?")

    # Should keep up to and including the edited message
    assert len(session.messages) == 3
    assert session.messages[2].content == "What's up?"
    assert session.metadata.message_count == 3


def test_edit_message_invalid_index():
    """Test editing with invalid index raises IndexError."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))

    with pytest.raises(IndexError):
        session.edit_message(5, "New content")


def test_edit_non_user_message():
    """Test editing a non-user message raises ValueError."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    now = datetime.utcnow().isoformat() + "Z"

    session.add_message(
        AssistantMessage(
            content="Hi!", model="llama3:8b", message_id="msg1", timestamp=now
        )
    )

    with pytest.raises(ValueError, match="Can only edit user messages"):
        session.edit_message(0, "New content")


def test_update_model():
    """Test updating the model updates metadata."""
    session = ChatSession(session_id="test123", model="llama3:8b")

    session.update_model("qwen3:14b")

    assert session.model == "qwen3:14b"
    assert session.metadata.model == "qwen3:14b"


def test_update_tool_settings():
    """Test updating tool settings."""
    session = ChatSession(session_id="test123", model="llama3:8b")

    new_settings = ToolSettings(
        tools=["tool1", "tool2"], tool_group="math", execution_policy="never_confirm"
    )
    session.update_tool_settings(new_settings)

    assert session.metadata.tool_settings.tools == ["tool1", "tool2"]
    assert session.metadata.tool_settings.tool_group == "math"
    assert session.metadata.tool_settings.execution_policy == "never_confirm"


def test_update_agent_settings():
    """Test updating agent settings."""
    session = ChatSession(session_id="test123", model="llama3:8b")

    new_settings = AgentSettings(enabled_agents=["agent1", "agent2"])
    session.update_agent_settings(new_settings)

    assert session.metadata.agent_settings.enabled_agents == ["agent1", "agent2"]


def test_to_dict():
    """Test converting session to dictionary."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))

    data = session.to_dict()

    assert "metadata" in data
    assert "messages" in data
    assert data["metadata"]["session_id"] == "test123"
    assert data["metadata"]["model"] == "llama3:8b"
    assert data["metadata"]["format_version"] == "1.3"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"


def test_save_and_load(tmp_path: Path):
    """Test saving and loading a session."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))
    session.add_message(
        AssistantMessage(
            content="Hi!", model="llama3:8b", message_id="msg2", timestamp=now
        )
    )

    # Save
    session.save(tmp_path)

    # Load
    loaded_session = ChatSession.load("test123", tmp_path)

    assert loaded_session.session_id == "test123"
    assert loaded_session.model == "llama3:8b"
    assert len(loaded_session.messages) == 2
    assert loaded_session.messages[0].content == "Hello"
    assert loaded_session.messages[1].content == "Hi!"


def test_load_nonexistent_session(tmp_path: Path):
    """Test loading a nonexistent session raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ChatSession.load("nonexistent", tmp_path)


def test_save_creates_directory(tmp_path: Path):
    """Test that save creates the directory if it doesn't exist."""
    sessions_dir = tmp_path / "nested" / "sessions"
    session = ChatSession(session_id="test123", model="llama3:8b")

    session.save(sessions_dir)

    assert sessions_dir.exists()
    assert (sessions_dir / "test123.json").exists()


def test_generate_session_id():
    """Test generating session IDs."""
    id1 = ChatSession.generate_session_id()
    id2 = ChatSession.generate_session_id()

    # Should be 10 characters
    assert len(id1) == 10
    assert len(id2) == 10

    # Should be different
    assert id1 != id2

    # Should be hexadecimal
    assert all(c in "0123456789abcdef" for c in id1)


def test_get_preview_empty_session():
    """Test getting preview from empty session."""
    session = ChatSession(session_id="test123", model="llama3:8b")

    preview = session.get_preview()

    assert preview == ""


def test_get_preview_with_user_message():
    """Test getting preview from session with user message."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.add_message(
        UserMessage(content="This is a test message", message_id="msg1", timestamp=now)
    )

    preview = session.get_preview()

    assert preview == "This is a test message"


def test_get_preview_truncated():
    """Test that long messages are truncated in preview."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    long_content = "a" * 200
    session.add_message(
        UserMessage(content=long_content, message_id="msg1", timestamp=now)
    )

    preview = session.get_preview(max_length=50)

    assert len(preview) == 50
    assert preview.endswith("...")


def test_get_preview_skips_system_messages():
    """Test that preview skips system messages and finds first user message."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.add_message(
        SystemMessage(
            content="You are a helpful assistant",
            message_id="msg1",
            timestamp=now,
        )
    )
    session.add_message(
        UserMessage(content="User's first message", message_id="msg2", timestamp=now)
    )

    preview = session.get_preview()

    assert preview == "User's first message"


def test_session_with_summary():
    """Test session with conversation summary."""
    summary = ConversationSummary(
        summary="Discussed Python programming", topics=["Python", "FastAPI"]
    )
    metadata = SessionMetadata(
        session_id="test123",
        model="llama3:8b",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        summary=summary,
        summary_model="qwen3:14b",
    )

    session = ChatSession(session_id="test123", model="llama3:8b", metadata=metadata)

    assert session.metadata.summary is not None
    assert session.metadata.summary.summary == "Discussed Python programming"
    assert session.metadata.summary.topics == ["Python", "FastAPI"]
    assert session.metadata.summary_model == "qwen3:14b"


def test_session_with_all_message_types(tmp_path: Path):
    """Test session with all message types can be saved and loaded."""
    now = datetime.utcnow().isoformat() + "Z"
    session = ChatSession(session_id="test123", model="llama3:8b")

    # Add all message types
    session.add_message(
        SystemMessage(
            content="You are helpful",
            source_file="helpful.md",
            message_id="msg1",
            timestamp=now,
        )
    )
    session.add_message(UserMessage(content="Hello", message_id="msg2", timestamp=now))
    session.add_message(
        AssistantMessage(
            content="Hi!",
            model="llama3:8b",
            message_id="msg3",
            timestamp=now,
            eval_count=10,
            prompt_eval_count=5,
            tool_calls=[{"function": {"name": "test", "arguments": {}}}],
        )
    )
    session.add_message(
        ToolMessage(
            tool_name="test_tool",
            content="result",
            message_id="msg4",
            timestamp=now,
        )
    )

    # Save and load
    session.save(tmp_path)
    loaded = ChatSession.load("test123", tmp_path)

    assert len(loaded.messages) == 4
    assert isinstance(loaded.messages[0], SystemMessage)
    assert isinstance(loaded.messages[1], UserMessage)
    assert isinstance(loaded.messages[2], AssistantMessage)
    assert isinstance(loaded.messages[3], ToolMessage)
    assert loaded.messages[0].source_file == "helpful.md"
    assert loaded.messages[2].eval_count == 10
    assert loaded.messages[3].tool_name == "test_tool"


def test_session_json_format(tmp_path: Path):
    """Test that saved JSON matches the expected format."""
    now = "2024-01-01T00:00:00Z"
    session = ChatSession(session_id="test123", model="llama3:8b")
    session.metadata.created_at = now
    session.metadata.updated_at = now
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))

    session.save(tmp_path)

    # Read and verify JSON structure
    with open(tmp_path / "test123.json", "r") as f:
        data = json.load(f)

    # Check metadata structure
    assert "metadata" in data
    assert data["metadata"]["session_id"] == "test123"
    assert data["metadata"]["model"] == "llama3:8b"
    assert data["metadata"]["format_version"] == "1.3"
    assert data["metadata"]["message_count"] == 1
    assert "tool_settings" in data["metadata"]
    assert "agent_settings" in data["metadata"]
    assert "context_window_config" in data["metadata"]

    # Check messages structure
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello"


def test_updated_at_changes():
    """Test that updated_at timestamp changes when modifying session."""
    session = ChatSession(session_id="test123", model="llama3:8b")
    original_updated = session.metadata.updated_at

    # Small delay to ensure timestamp changes
    import time

    time.sleep(0.01)

    now = datetime.utcnow().isoformat() + "Z"
    session.add_message(UserMessage(content="Hello", message_id="msg1", timestamp=now))

    assert session.metadata.updated_at != original_updated
