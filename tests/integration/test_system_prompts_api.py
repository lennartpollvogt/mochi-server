"""Integration tests for system prompts API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_system_prompts_empty(async_client, test_app):
    """Test listing system prompts when directory is empty."""
    response = await async_client.get("/api/v1/system-prompts")

    assert response.status_code == 200
    data = response.json()
    assert "prompts" in data
    assert data["prompts"] == []


@pytest.mark.asyncio
async def test_create_system_prompt(async_client, test_app):
    """Test creating a new system prompt."""
    request_data = {
        "filename": "helpful.md",
        "content": "You are a helpful assistant.",
    }

    response = await async_client.post("/api/v1/system-prompts", json=request_data)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "helpful.md"
    assert data["content"] == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_create_system_prompt_invalid_extension(async_client, test_app):
    """Test creating a prompt with invalid extension fails."""
    request_data = {
        "filename": "invalid.txt",
        "content": "Content",
    }

    response = await async_client.post("/api/v1/system-prompts", json=request_data)

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_system_prompt_empty_content(async_client, test_app):
    """Test creating a prompt with empty content fails."""
    request_data = {
        "filename": "empty.md",
        "content": "",
    }

    response = await async_client.post("/api/v1/system-prompts", json=request_data)

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_system_prompt_whitespace_only(async_client, test_app):
    """Test creating a prompt with whitespace-only content fails."""
    request_data = {
        "filename": "whitespace.md",
        "content": "   \n\t  ",
    }

    response = await async_client.post("/api/v1/system-prompts", json=request_data)

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_system_prompt_too_long(async_client, test_app):
    """Test creating a prompt that exceeds max length fails."""
    request_data = {
        "filename": "toolong.md",
        "content": "A" * 20001,
    }

    response = await async_client.post("/api/v1/system-prompts", json=request_data)

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_system_prompt_already_exists(async_client, test_app):
    """Test creating a duplicate prompt fails."""
    request_data = {
        "filename": "duplicate.md",
        "content": "Content",
    }

    # Create first time
    response1 = await async_client.post("/api/v1/system-prompts", json=request_data)
    assert response1.status_code == 201

    # Try to create again
    response2 = await async_client.post("/api/v1/system-prompts", json=request_data)
    assert response2.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_list_system_prompts_with_files(async_client, test_app):
    """Test listing system prompts with multiple files."""
    # Create prompts
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "helpful.md", "content": "You are helpful."},
    )
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "coder.md", "content": "You are an expert programmer. " * 50},
    )

    # List prompts
    response = await async_client.get("/api/v1/system-prompts")

    assert response.status_code == 200
    data = response.json()
    assert len(data["prompts"]) == 2

    # Check sorting (alphabetical)
    assert data["prompts"][0]["filename"] == "coder.md"
    assert data["prompts"][1]["filename"] == "helpful.md"

    # Check metadata
    helpful = data["prompts"][1]
    assert helpful["preview"] == "You are helpful."
    assert helpful["word_count"] == 3


@pytest.mark.asyncio
async def test_list_prompts_long_content_truncated(async_client, test_app):
    """Test that preview is truncated to 250 characters."""
    long_content = "A" * 300

    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "long.md", "content": long_content},
    )

    response = await async_client.get("/api/v1/system-prompts")

    assert response.status_code == 200
    data = response.json()
    assert len(data["prompts"]) == 1
    assert len(data["prompts"][0]["preview"]) == 250
    assert data["prompts"][0]["preview"].endswith("...")


@pytest.mark.asyncio
async def test_get_system_prompt(async_client, test_app):
    """Test getting a specific system prompt."""
    content = "You are a helpful assistant."

    # Create prompt
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "helpful.md", "content": content},
    )

    # Get prompt
    response = await async_client.get("/api/v1/system-prompts/helpful.md")

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "helpful.md"
    assert data["content"] == content


@pytest.mark.asyncio
async def test_get_system_prompt_not_found(async_client, test_app):
    """Test getting a non-existent prompt returns 404."""
    response = await async_client.get("/api/v1/system-prompts/nonexistent.md")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_system_prompt(async_client, test_app):
    """Test updating an existing system prompt."""
    # Create prompt
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "test.md", "content": "Old content"},
    )

    # Update prompt
    new_content = "New content"
    response = await async_client.put(
        "/api/v1/system-prompts/test.md",
        json={"content": new_content},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.md"
    assert data["content"] == new_content

    # Verify update persisted
    get_response = await async_client.get("/api/v1/system-prompts/test.md")
    assert get_response.json()["content"] == new_content


@pytest.mark.asyncio
async def test_update_system_prompt_not_found(async_client, test_app):
    """Test updating a non-existent prompt returns 404."""
    response = await async_client.put(
        "/api/v1/system-prompts/nonexistent.md",
        json={"content": "New content"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_system_prompt_invalid_content(async_client, test_app):
    """Test updating with invalid content fails."""
    # Create prompt
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "test.md", "content": "Content"},
    )

    # Try to update with empty content
    response = await async_client.put(
        "/api/v1/system-prompts/test.md",
        json={"content": ""},
    )

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_delete_system_prompt(async_client, test_app):
    """Test deleting a system prompt."""
    # Create prompt
    await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "todelete.md", "content": "Content"},
    )

    # Delete prompt
    response = await async_client.delete("/api/v1/system-prompts/todelete.md")

    assert response.status_code == 204

    # Verify deletion
    get_response = await async_client.get("/api/v1/system-prompts/todelete.md")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_system_prompt_not_found(async_client, test_app):
    """Test deleting a non-existent prompt returns 404."""
    response = await async_client.delete("/api/v1/system-prompts/nonexistent.md")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_system_prompt_with_unicode(async_client, test_app):
    """Test creating and retrieving prompts with unicode characters."""
    content = "你好世界 こんにちは 🌍"

    # Create
    response = await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "unicode.md", "content": content},
    )
    assert response.status_code == 201

    # Retrieve
    get_response = await async_client.get("/api/v1/system-prompts/unicode.md")
    assert get_response.status_code == 200
    assert get_response.json()["content"] == content


@pytest.mark.asyncio
async def test_create_prompt_with_path_separator(async_client, test_app):
    """Test that filenames with path separators are rejected."""
    response = await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": "../evil.md", "content": "Content"},
    )

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_system_prompt_crud_workflow(async_client, test_app):
    """Test complete CRUD workflow for system prompts."""
    filename = "workflow.md"

    # Create
    create_response = await async_client.post(
        "/api/v1/system-prompts",
        json={"filename": filename, "content": "Initial content"},
    )
    assert create_response.status_code == 201

    # Read
    read_response = await async_client.get(f"/api/v1/system-prompts/{filename}")
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "Initial content"

    # Update
    update_response = await async_client.put(
        f"/api/v1/system-prompts/{filename}",
        json={"content": "Updated content"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "Updated content"

    # List (should include our file)
    list_response = await async_client.get("/api/v1/system-prompts")
    assert list_response.status_code == 200
    filenames = [p["filename"] for p in list_response.json()["prompts"]]
    assert filename in filenames

    # Delete
    delete_response = await async_client.delete(f"/api/v1/system-prompts/{filename}")
    assert delete_response.status_code == 204

    # Verify deletion
    final_response = await async_client.get(f"/api/v1/system-prompts/{filename}")
    assert final_response.status_code == 404
