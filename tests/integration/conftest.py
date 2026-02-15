"""Pytest configuration for integration tests.

This module provides integration-test-specific fixtures that ensure
proper test isolation and mocking for API endpoint tests.
"""

import pytest


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
