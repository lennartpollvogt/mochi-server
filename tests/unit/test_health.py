"""Unit tests for the health check endpoint."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_health_check_returns_ok(async_client):
    """Test that health check returns status ok."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_check_response_structure(async_client):
    """Test that health check response has correct structure."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    # Required fields
    assert "status" in data
    assert "version" in data
    assert "ollama_connected" in data
    assert "ollama_host" in data


@pytest.mark.asyncio
async def test_health_check_version_format(async_client):
    """Test that version follows semantic versioning format."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    version = data["version"]
    # Basic check for semantic versioning format (X.Y.Z)
    parts = version.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.asyncio
async def test_health_check_content_type(async_client):
    """Test that health check returns JSON content type."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_health_check_with_ollama_connected(async_client, test_app):
    """Test health check when Ollama is connected."""
    # Mock a connected Ollama client
    mock_client = AsyncMock()
    mock_client.host = "http://localhost:11434"
    mock_client.check_connection.return_value = True
    test_app.state.ollama_client = mock_client

    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ollama_connected"] is True
    assert data["ollama_host"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_health_check_with_ollama_disconnected(async_client, test_app):
    """Test health check when Ollama is not reachable."""
    # Mock a disconnected Ollama client
    mock_client = AsyncMock()
    mock_client.host = "http://localhost:11434"
    mock_client.check_connection.return_value = False
    test_app.state.ollama_client = mock_client

    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"  # Server is still healthy
    assert data["ollama_connected"] is False
    assert data["ollama_host"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_health_check_ollama_check_exception(async_client, test_app):
    """Test health check when Ollama connectivity check raises exception."""
    # Mock Ollama client that raises exception
    mock_client = AsyncMock()
    mock_client.host = "http://localhost:11434"
    mock_client.check_connection.side_effect = Exception("Connection error")
    test_app.state.ollama_client = mock_client

    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"  # Server is still healthy
    assert data["ollama_connected"] is False  # Connection failed
    assert data["ollama_host"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_health_check_no_ollama_client(async_client, test_app):
    """Test health check when Ollama client is not initialized."""
    # Remove the Ollama client to simulate it not being initialized
    if hasattr(test_app.state, "ollama_client"):
        delattr(test_app.state, "ollama_client")

    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ollama_connected"] is None
    assert data["ollama_host"] is None
