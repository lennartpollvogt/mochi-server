"""Unit tests for the models API endpoints."""

from unittest.mock import AsyncMock

import pytest

from mochi_server.ollama import ModelInfo


@pytest.fixture
def mock_ollama_client():
    """Create a mock OllamaClient."""
    mock = AsyncMock()
    mock.host = "http://localhost:11434"
    return mock


@pytest.fixture
def sample_model_infos():
    """Create sample ModelInfo instances for testing."""
    return [
        ModelInfo(
            name="llama3:8b",
            size_mb=4445.1,
            format="gguf",
            family="llama",
            parameter_size="8.0B",
            quantization_level="Q4_0",
            capabilities=["completion", "tools"],
            context_length=8192,
        ),
        ModelInfo(
            name="qwen2.5:14b",
            size_mb=8629.5,
            format="gguf",
            family="qwen2",
            parameter_size="14.8B",
            quantization_level="Q4_K_M",
            capabilities=["completion"],
            context_length=32768,
        ),
    ]


@pytest.mark.asyncio
async def test_list_models_success(
    async_client, test_app, mock_ollama_client, sample_model_infos
):
    """Test successful model listing."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.list_models.return_value = sample_model_infos

    response = await async_client.get("/api/v1/models")

    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 2

    # Check first model
    model1 = data["models"][0]
    assert model1["name"] == "llama3:8b"
    assert model1["size_mb"] == 4445.1
    assert model1["format"] == "gguf"
    assert model1["family"] == "llama"
    assert model1["parameter_size"] == "8.0B"
    assert model1["quantization_level"] == "Q4_0"
    assert model1["capabilities"] == ["completion", "tools"]
    assert model1["context_length"] == 8192

    # Check second model
    model2 = data["models"][1]
    assert model2["name"] == "qwen2.5:14b"
    assert model2["context_length"] == 32768


@pytest.mark.asyncio
async def test_list_models_empty(async_client, test_app, mock_ollama_client):
    """Test listing models when none are available."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.list_models.return_value = []

    response = await async_client.get("/api/v1/models")

    assert response.status_code == 200
    data = response.json()
    assert data["models"] == []


@pytest.mark.asyncio
async def test_list_models_ollama_error(async_client, test_app, mock_ollama_client):
    """Test list models when Ollama API fails."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.list_models.side_effect = Exception("Connection error")

    response = await async_client.get("/api/v1/models")

    assert response.status_code == 502
    data = response.json()
    assert "detail" in data
    assert "Failed to communicate with Ollama" in data["detail"]


@pytest.mark.asyncio
async def test_list_models_client_not_initialized(async_client, test_app):
    """Test list models when Ollama client is not initialized."""
    # Remove the Ollama client to simulate it not being initialized
    if hasattr(test_app.state, "ollama_client"):
        delattr(test_app.state, "ollama_client")

    response = await async_client.get("/api/v1/models")

    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "Ollama client not initialized" in data["detail"]


@pytest.mark.asyncio
async def test_get_model_detail_success(
    async_client, test_app, mock_ollama_client, sample_model_infos
):
    """Test getting details for a specific model."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.get_model_info.return_value = sample_model_infos[0]

    response = await async_client.get("/api/v1/models/llama3:8b")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "llama3:8b"
    assert data["size_mb"] == 4445.1
    assert data["format"] == "gguf"
    assert data["family"] == "llama"
    assert data["parameter_size"] == "8.0B"
    assert data["quantization_level"] == "Q4_0"
    assert data["capabilities"] == ["completion", "tools"]
    assert data["context_length"] == 8192


@pytest.mark.asyncio
async def test_get_model_detail_not_found(async_client, test_app, mock_ollama_client):
    """Test getting details for a non-existent model."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.get_model_info.return_value = None

    response = await async_client.get("/api/v1/models/nonexistent:model")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_model_detail_ollama_error(
    async_client, test_app, mock_ollama_client
):
    """Test getting model details when Ollama API fails."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.get_model_info.side_effect = Exception("API error")

    response = await async_client.get("/api/v1/models/llama3:8b")

    assert response.status_code == 502
    data = response.json()
    assert "detail" in data
    assert "Failed to communicate with Ollama" in data["detail"]


@pytest.mark.asyncio
async def test_get_model_detail_client_not_initialized(async_client, test_app):
    """Test getting model details when Ollama client is not initialized."""
    # Remove the Ollama client to simulate it not being initialized
    if hasattr(test_app.state, "ollama_client"):
        delattr(test_app.state, "ollama_client")

    response = await async_client.get("/api/v1/models/llama3:8b")

    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "Ollama client not initialized" in data["detail"]


@pytest.mark.asyncio
async def test_get_model_detail_with_colon_in_name(
    async_client, test_app, mock_ollama_client, sample_model_infos
):
    """Test that model names with colons are handled correctly."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.get_model_info.return_value = sample_model_infos[0]

    # The :path parameter type should handle colons correctly
    response = await async_client.get("/api/v1/models/llama3:8b")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "llama3:8b"
    mock_ollama_client.get_model_info.assert_called_once_with("llama3:8b")


@pytest.mark.asyncio
async def test_models_response_schema_validation(
    async_client, test_app, mock_ollama_client, sample_model_infos
):
    """Test that the response schema is validated correctly."""
    test_app.state.ollama_client = mock_ollama_client
    mock_ollama_client.list_models.return_value = sample_model_infos

    response = await async_client.get("/api/v1/models")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    for model in data["models"]:
        assert "name" in model
        assert "size_mb" in model
        assert "format" in model
        assert "family" in model
        assert "parameter_size" in model
        assert "quantization_level" in model
        assert "capabilities" in model
        assert "context_length" in model

        # Verify types
        assert isinstance(model["name"], str)
        assert isinstance(model["size_mb"], (int, float))
        assert isinstance(model["format"], str)
        assert isinstance(model["family"], str)
        assert isinstance(model["parameter_size"], str)
        assert isinstance(model["quantization_level"], str)
        assert isinstance(model["capabilities"], list)
        assert isinstance(model["context_length"], int)
