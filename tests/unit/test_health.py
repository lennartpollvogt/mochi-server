"""Unit tests for the health check endpoint."""

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

    # Required fields in Phase 0
    assert "status" in data
    assert "version" in data

    # Optional fields (None in Phase 0, added in Phase 1+)
    assert "ollama_connected" in data
    assert "ollama_host" in data
    assert data["ollama_connected"] is None
    assert data["ollama_host"] is None


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
