"""Pytest configuration for integration tests.

This module provides integration-test-specific fixtures that ensure
proper test isolation and mocking for API endpoint tests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from mochi_server.ollama import ModelInfo


@pytest.fixture(autouse=True)
def mock_ollama_client():
    """Mock OllamaClient for all integration tests.

    This fixture patches the OllamaClient class before the app is created,
    ensuring the lifespan uses our mock instead of creating a real client.
    """
    with patch("mochi_server.app.OllamaClient") as mock_client_class:
        # Create the mock instance
        mock_instance = AsyncMock()
        mock_instance.check_connection.return_value = True
        mock_instance.list_models.return_value = [
            ModelInfo(
                name="llama3.2:latest",
                size_mb=4445.3,
                format="gguf",
                family="llama",
                parameter_size="3.2B",
                quantization_level="Q4_0",
                capabilities=["completion"],
                context_length=8192,
            ),
        ]
        mock_instance.get_model_info.return_value = ModelInfo(
            name="llama3.2:latest",
            size_mb=4445.3,
            format="gguf",
            family="llama",
            parameter_size="3.2B",
            quantization_level="Q4_0",
            capabilities=["completion"],
            context_length=8192,
        )

        # Return the mock instance when OllamaClient is instantiated
        mock_client_class.return_value = mock_instance

        yield mock_instance


@pytest.fixture(autouse=True)
def clean_session_dir(test_settings):
    """Ensure sessions directory is clean before each test.

    This fixture runs automatically before each test to remove any
    session files from the previous test, ensuring test isolation.

    Args:
        test_settings: The test settings fixture from parent conftest
    """
    sessions_dir = test_settings.resolved_sessions_dir

    # Clean up any existing session files before the test
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            session_file.unlink()

    yield

    # Optional: Clean up after test as well
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            session_file.unlink()
