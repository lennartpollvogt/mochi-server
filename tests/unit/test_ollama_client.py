"""Unit tests for the OllamaClient wrapper."""

from unittest.mock import AsyncMock, patch

import pytest

from mochi_server.ollama import ModelInfo, OllamaClient


@pytest.fixture
def mock_ollama_async_client():
    """Create a mock ollama.AsyncClient."""
    with patch("mochi_server.ollama.client.ollama.AsyncClient") as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def ollama_client(mock_ollama_async_client):
    """Create an OllamaClient with mocked AsyncClient."""
    return OllamaClient(host="http://localhost:11434")


@pytest.mark.asyncio
async def test_client_initialization():
    """Test that OllamaClient initializes correctly."""
    with patch("mochi_server.ollama.client.ollama.AsyncClient"):
        client = OllamaClient(host="http://test:11434")
        assert client.host == "http://test:11434"
        assert client._client is not None


@pytest.mark.asyncio
async def test_check_connection_success(ollama_client, mock_ollama_async_client):
    """Test successful connection check."""
    mock_ollama_async_client.list.return_value = {"models": []}

    result = await ollama_client.check_connection()

    assert result is True
    mock_ollama_async_client.list.assert_called_once()


@pytest.mark.asyncio
async def test_check_connection_failure(ollama_client, mock_ollama_async_client):
    """Test connection check when Ollama is unreachable."""
    mock_ollama_async_client.list.side_effect = Exception("Connection refused")

    result = await ollama_client.check_connection()

    assert result is False


@pytest.mark.asyncio
async def test_list_models_success(ollama_client, mock_ollama_async_client):
    """Test listing models successfully."""
    # Mock the list response with object-like structure
    from unittest.mock import MagicMock

    mock_model1 = MagicMock()
    mock_model1.model = "llama3:8b"
    mock_model1.size = 4661211136

    mock_model2 = MagicMock()
    mock_model2.model = "qwen2.5:14b"
    mock_model2.size = 9048248320

    mock_list_response = MagicMock()
    mock_list_response.models = [mock_model1, mock_model2]
    mock_ollama_async_client.list.return_value = mock_list_response

    # Mock the show responses
    mock_show1 = MagicMock()
    mock_show1.capabilities = ["completion", "tools"]
    mock_show1.modelinfo = {"llama.context_length": 8192}
    mock_details1 = MagicMock()
    mock_details1.format = "gguf"
    mock_details1.family = "llama"
    mock_details1.parameter_size = "8.0B"
    mock_details1.quantization_level = "Q4_0"
    mock_show1.details = mock_details1

    mock_show2 = MagicMock()
    mock_show2.capabilities = ["completion"]
    mock_show2.modelinfo = {"qwen2.context_length": 32768}
    mock_details2 = MagicMock()
    mock_details2.format = "gguf"
    mock_details2.family = "qwen2"
    mock_details2.parameter_size = "14.8B"
    mock_details2.quantization_level = "Q4_K_M"
    mock_show2.details = mock_details2

    mock_ollama_async_client.show.side_effect = [mock_show1, mock_show2]

    result = await ollama_client.list_models()

    assert len(result) == 2
    assert all(isinstance(model, ModelInfo) for model in result)
    assert result[0].name == "llama3:8b"
    assert result[0].size_mb == 4445.3
    assert result[0].family == "llama"
    assert result[0].context_length == 8192
    assert "completion" in result[0].capabilities
    assert "tools" in result[0].capabilities

    assert result[1].name == "qwen2.5:14b"
    assert result[1].context_length == 32768


@pytest.mark.asyncio
async def test_list_models_filters_non_completion(
    ollama_client, mock_ollama_async_client
):
    """Test that non-completion models are filtered out."""
    from unittest.mock import MagicMock

    mock_model1 = MagicMock()
    mock_model1.model = "llama3:8b"
    mock_model1.size = 4661211136

    mock_model2 = MagicMock()
    mock_model2.model = "nomic-embed-text"
    mock_model2.size = 548118528

    mock_list_response = MagicMock()
    mock_list_response.models = [mock_model1, mock_model2]
    mock_ollama_async_client.list.return_value = mock_list_response

    mock_show1 = MagicMock()
    mock_show1.capabilities = ["completion"]
    mock_show1.modelinfo = {"llama.context_length": 8192}
    mock_details1 = MagicMock()
    mock_details1.format = "gguf"
    mock_details1.family = "llama"
    mock_details1.parameter_size = "8.0B"
    mock_details1.quantization_level = "Q4_0"
    mock_show1.details = mock_details1

    mock_show2 = MagicMock()
    mock_show2.capabilities = ["embedding"]  # No completion
    mock_show2.modelinfo = {"nomic-bert.context_length": 8192}
    mock_details2 = MagicMock()
    mock_details2.format = "gguf"
    mock_details2.family = "nomic-bert"
    mock_details2.parameter_size = "137M"
    mock_details2.quantization_level = "F16"
    mock_show2.details = mock_details2

    mock_ollama_async_client.show.side_effect = [mock_show1, mock_show2]

    result = await ollama_client.list_models()

    # Only the completion model should be included
    assert len(result) == 1
    assert result[0].name == "llama3:8b"


@pytest.mark.asyncio
async def test_list_models_empty(ollama_client, mock_ollama_async_client):
    """Test listing models when none are available."""
    from unittest.mock import MagicMock

    mock_list_response = MagicMock()
    mock_list_response.models = []
    mock_ollama_async_client.list.return_value = mock_list_response

    result = await ollama_client.list_models()

    assert result == []


@pytest.mark.asyncio
async def test_list_models_api_error(ollama_client, mock_ollama_async_client):
    """Test list_models when Ollama API fails."""
    mock_ollama_async_client.list.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        await ollama_client.list_models()


@pytest.mark.asyncio
async def test_get_model_info_success(ollama_client, mock_ollama_async_client):
    """Test getting model info successfully."""
    from unittest.mock import MagicMock

    # Mock the list response
    mock_model = MagicMock()
    mock_model.model = "llama3:8b"
    mock_model.size = 4661211136

    mock_list_response = MagicMock()
    mock_list_response.models = [mock_model]
    mock_ollama_async_client.list.return_value = mock_list_response

    # Mock the show response
    mock_show = MagicMock()
    mock_show.capabilities = ["completion", "tools"]
    mock_show.modelinfo = {"llama.context_length": 8192}
    mock_details = MagicMock()
    mock_details.format = "gguf"
    mock_details.family = "llama"
    mock_details.parameter_size = "8.0B"
    mock_details.quantization_level = "Q4_0"
    mock_show.details = mock_details
    mock_ollama_async_client.show.return_value = mock_show

    result = await ollama_client.get_model_info("llama3:8b")

    assert result is not None
    assert isinstance(result, ModelInfo)
    assert result.name == "llama3:8b"
    assert result.size_mb == 4445.3
    assert result.family == "llama"
    assert result.capabilities == ["completion", "tools"]


@pytest.mark.asyncio
async def test_get_model_info_not_found(ollama_client, mock_ollama_async_client):
    """Test getting model info when model doesn't exist."""
    from unittest.mock import MagicMock

    # Mock list response with no matching model
    mock_list_response = MagicMock()
    mock_list_response.models = []
    mock_ollama_async_client.list.return_value = mock_list_response

    result = await ollama_client.get_model_info("nonexistent:model")

    assert result is None


@pytest.mark.asyncio
async def test_get_model_info_api_error(ollama_client, mock_ollama_async_client):
    """Test get_model_info when Ollama API fails."""
    # Mock list() to fail
    mock_ollama_async_client.list.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        await ollama_client.get_model_info("llama3:8b")


@pytest.mark.asyncio
async def test_close(ollama_client):
    """Test that close method can be called without errors."""
    await ollama_client.close()
    # Should not raise any exceptions


def test_model_info_from_ollama_model():
    """Test ModelInfo.from_ollama_model static method."""
    ollama_data = {
        "model": "qwen3:14b",
        "size": 9048248320,
        "details": {
            "format": "gguf",
            "family": "qwen3",
            "parameter_size": "14.8B",
            "quantization_level": "Q4_K_M",
        },
        "capabilities": ["completion", "tools"],
        "modelinfo": {
            "qwen3.context_length": 40960,
        },
    }

    model_info = ModelInfo.from_ollama_model(ollama_data)

    assert model_info.name == "qwen3:14b"
    assert model_info.size_mb == 8629.1
    assert model_info.format == "gguf"
    assert model_info.family == "qwen3"
    assert model_info.parameter_size == "14.8B"
    assert model_info.quantization_level == "Q4_K_M"
    assert model_info.capabilities == ["completion", "tools"]
    assert model_info.context_length == 40960


def test_model_info_from_ollama_model_defaults():
    """Test ModelInfo.from_ollama_model with minimal data."""
    ollama_data = {
        "model": "test:model",
        "size": 1073741824,  # 1GB
        "details": {},
        "modelinfo": {},
    }

    model_info = ModelInfo.from_ollama_model(ollama_data)

    assert model_info.name == "test:model"
    assert model_info.size_mb == 1024.0
    assert model_info.format == "unknown"
    assert model_info.family == "unknown"
    assert model_info.parameter_size == "unknown"
    assert model_info.quantization_level == "unknown"
    assert model_info.capabilities == ["completion"]  # Default
    assert model_info.context_length == 2048  # Default


def test_model_info_from_ollama_model_fallback_context():
    """Test ModelInfo context_length fallback logic."""
    # Test with generic context_length key
    ollama_data = {
        "model": "test:model",
        "size": 1000000000,
        "details": {"family": "test"},
        "modelinfo": {"context_length": 16384},
    }

    model_info = ModelInfo.from_ollama_model(ollama_data)
    assert model_info.context_length == 16384
