"""Unit tests for the FastAPI app factory and configuration."""

from fastapi import FastAPI

from mochi_server import __version__, create_app
from mochi_server.config import MochiServerSettings


def test_create_app_returns_fastapi_instance():
    """Test that create_app returns a FastAPI instance."""
    app = create_app()
    assert isinstance(app, FastAPI)


def test_create_app_with_settings(test_settings):
    """Test that create_app accepts custom settings."""
    app = create_app(settings=test_settings)
    assert isinstance(app, FastAPI)


def test_create_app_metadata():
    """Test that app has correct metadata."""
    app = create_app()
    assert app.title == "mochi-server"
    assert app.version == "0.1.0"
    assert "Headless FastAPI server" in app.description


def test_create_app_includes_health_router():
    """Test that health router is registered."""
    app = create_app()

    # Check that the health endpoint route exists
    routes = [route.path for route in app.routes]  # type: ignore[attr-defined]
    assert "/api/v1/health" in routes


def test_create_app_has_cors_middleware(test_settings):
    """Test that CORS middleware is configured."""
    app = create_app(settings=test_settings)

    # Check that CORSMiddleware is in the middleware stack
    # FastAPI wraps middleware, so we check middleware_stack instead
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]  # type: ignore[attr-defined]
    assert "CORSMiddleware" in middleware_classes


def test_version_constant():
    """Test that __version__ is defined and matches app version."""
    assert __version__ == "0.1.0"


def test_settings_default_values():
    """Test that settings have correct default values."""
    settings = MochiServerSettings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.ollama_host == "http://localhost:11434"
    assert settings.data_dir == "."
    assert settings.log_level == "INFO"
    assert settings.summarization_enabled is True
    assert settings.dynamic_context_window_enabled is True
    assert settings.max_agent_iterations == 50


def test_settings_env_prefix(monkeypatch):
    """Test that settings respect MOCHI_ environment variable prefix."""
    monkeypatch.setenv("MOCHI_PORT", "9000")
    monkeypatch.setenv("MOCHI_OLLAMA_HOST", "http://custom:11434")

    settings = MochiServerSettings()

    assert settings.port == 9000
    assert settings.ollama_host == "http://custom:11434"


def test_settings_resolved_paths(tmp_path):
    """Test that resolved path properties work correctly."""
    settings = MochiServerSettings(data_dir=str(tmp_path))

    assert settings.resolved_sessions_dir == tmp_path / "chat_sessions"
    assert settings.resolved_tools_dir == tmp_path / "tools"
    assert settings.resolved_agents_dir == tmp_path / "agents"
    assert settings.resolved_agent_chats_dir == tmp_path / "agents" / "agent_chats"
    assert settings.resolved_system_prompts_dir == tmp_path / "system_prompts"
    assert (
        settings.resolved_planning_prompt_path
        == tmp_path / "docs" / "agents" / "agent_prompt_planning.md"
    )
    assert (
        settings.resolved_execution_prompt_path
        == tmp_path / "docs" / "agents" / "agent_prompt_execution.md"
    )


def test_settings_custom_directories(tmp_path):
    """Test that custom directory paths are respected."""
    settings = MochiServerSettings(
        data_dir=str(tmp_path),
        sessions_dir="my_sessions",
        tools_dir="my_tools",
    )

    assert settings.resolved_sessions_dir == tmp_path / "my_sessions"
    assert settings.resolved_tools_dir == tmp_path / "my_tools"
