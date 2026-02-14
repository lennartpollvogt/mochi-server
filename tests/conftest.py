"""Pytest configuration and shared fixtures for mochi-server tests.

This module provides common fixtures used across all test modules,
including test app creation and async client setup.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from mochi_server import create_app
from mochi_server.config import MochiServerSettings


@pytest.fixture
def test_settings(tmp_path):
    """Create test settings with isolated temporary directories.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.

    Returns:
        MochiServerSettings: Settings instance configured for testing.
    """
    return MochiServerSettings(
        host="127.0.0.1",
        port=8000,
        ollama_host="http://localhost:11434",
        data_dir=str(tmp_path),
        sessions_dir="chat_sessions",
        tools_dir="tools",
        agents_dir="agents",
        agent_chats_dir="agents/agent_chats",
        system_prompts_dir="system_prompts",
        log_level="DEBUG",
        cors_origins=["*"],
    )


@pytest.fixture
def test_app(test_settings):
    """Create a FastAPI test application instance.

    Args:
        test_settings: Test settings fixture.

    Returns:
        FastAPI: Configured test application.
    """
    return create_app(settings=test_settings)


@pytest_asyncio.fixture
async def async_client(test_app):
    """Create an async HTTP client for testing FastAPI endpoints.

    Args:
        test_app: Test application fixture.

    Yields:
        AsyncClient: Async HTTP client for making test requests.
    """
    # Trigger the lifespan startup manually for tests
    async with test_app.router.lifespan_context(test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
