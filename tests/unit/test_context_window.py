"""Unit tests for DynamicContextWindowService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mochi_server.services.context_window import (
    ContextWindowCalculation,
    DynamicContextWindowService,
)


@pytest.fixture
def mock_ollama_client():
    """Create a mock Ollama client."""
    client = MagicMock()
    client.get_model_info = AsyncMock()
    return client


@pytest.fixture
def context_window_service(mock_ollama_client):
    """Create a DynamicContextWindowService with mock client."""
    return DynamicContextWindowService(ollama_client=mock_ollama_client)


class TestGetModelMaxContext:
    """Tests for get_model_max_context method."""

    @pytest.mark.asyncio
    async def test_get_model_max_context_success(
        self, context_window_service, mock_ollama_client
    ):
        """Test successful retrieval of model max context."""
        # Arrange
        mock_model_info = MagicMock()
        mock_model_info.context_length = 40960
        mock_ollama_client.get_model_info.return_value = mock_model_info

        # Act
        result = await context_window_service.get_model_max_context("qwen3:14b")

        # Assert
        assert result == 40960
        mock_ollama_client.get_model_info.assert_called_once_with("qwen3:14b")

    @pytest.mark.asyncio
    async def test_get_model_max_context_not_found(
        self, context_window_service, mock_ollama_client
    ):
        """Test when model info is not found."""
        # Arrange
        mock_ollama_client.get_model_info.return_value = None

        # Act
        result = await context_window_service.get_model_max_context("unknown_model")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_model_max_context_error(
        self, context_window_service, mock_ollama_client
    ):
        """Test when getting model info raises an exception."""
        # Arrange
        mock_ollama_client.get_model_info.side_effect = Exception("Connection error")

        # Act
        result = await context_window_service.get_model_max_context("qwen3:14b")

        # Assert
        assert result is None


class TestCalculateContextWindow:
    """Tests for calculate_context_window method."""

    def test_manual_override_keeps_current_window(self, context_window_service):
        """Test that manual override keeps the current window."""
        # Act
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=16384,
            dynamic_enabled=True,
            manual_override=True,
            model_max_context=40960,
            usage_tokens=1000,
            last_adjustment_reason="initial_setup",
        )

        # Assert
        assert result.current_window == 16384
        assert result.reason == "manual_override"

    def test_dynamic_disabled_keeps_current_window(self, context_window_service):
        """Test that disabled dynamic keeps the current window."""
        # Act
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=16384,
            dynamic_enabled=False,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=1000,
            last_adjustment_reason="initial_setup",
        )

        # Assert
        assert result.current_window == 16384
        assert result.reason == "no_adjustment"

    def test_new_conversation_uses_initial_window(self, context_window_service):
        """Test that new conversations use the initial window."""
        # Act
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=8192,
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=0,  # New conversation
            last_adjustment_reason="initial_setup",
        )

        # Assert
        # Should use min(safe_limit, 8192) = min(40960 * 0.9, 8192) = min(36864, 8192) = 8192
        assert result.current_window == 8192
        assert result.reason == "no_adjustment"

    def test_new_conversation_sets_initial_window_when_different(
        self, context_window_service
    ):
        """Test that new conversations set initial window when current is different."""
        # Act
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=2048,  # Different from default
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=0,  # New conversation
            last_adjustment_reason="initial_setup",
        )

        # Assert
        # Should use min(safe_limit, 8192) = min(40960 * 0.9, 8192) = min(36864, 8192) = 8192
        assert result.current_window == 8192
        assert result.reason == "initial_setup"

    def test_ongoing_conversation_no_adjustment_needed(self, context_window_service):
        """Test ongoing conversation that doesn't need adjustment."""
        # Act
        # With 50% threshold, 2000 tokens usage requires 4000 window
        # Current is 8192, so no adjustment needed
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=8192,
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=2000,
            last_adjustment_reason="initial_setup",
        )

        # Assert
        assert result.current_window == 8192
        assert result.reason == "no_adjustment"

    def test_usage_threshold_increases_window(self, context_window_service):
        """Test that usage threshold triggers window increase."""
        # Act
        # With 50% threshold, 10000 tokens usage requires 20000 window
        # Current is 8192, so adjustment needed
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=8192,
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=10000,
            last_adjustment_reason="initial_setup",
        )

        # Assert
        # Required: 10000 / 0.5 = 20000
        # Safe limit: 40960 * 0.9 = 36864
        # Should be min(20000, 36864) = 20000
        assert result.current_window == 20000
        assert result.reason == "usage_threshold"

    def test_window_not_exceed_safe_limit(self, context_window_service):
        """Test that window doesn't exceed safe limit."""
        # Act
        # With very high usage, should cap at safe limit
        result = context_window_service.calculate_context_window(
            model="qwen3:14b",
            current_window=8192,
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=40960,
            usage_tokens=50000,  # Very high usage
            last_adjustment_reason="initial_setup",
        )

        # Assert
        # Required: 50000 / 0.5 = 100000
        # Safe limit: 40960 * 0.9 = 36864
        # Should be capped at safe limit: 36864
        assert result.current_window == 36864
        assert result.reason == "usage_threshold"

    def test_no_model_max_context_uses_default(self, context_window_service):
        """Test handling when model max context is not available."""
        # Act
        result = context_window_service.calculate_context_window(
            model="unknown_model",
            current_window=2048,
            dynamic_enabled=True,
            manual_override=False,
            model_max_context=None,
            usage_tokens=0,
            last_adjustment_reason="initial_setup",
        )

        # Assert
        # Should use default_initial_window when model_max_context is None
        assert result.current_window == context_window_service.default_initial_window
        assert result.model_max_context is None


class TestGetNumCtxOptions:
    """Tests for get_num_ctx_options method."""

    def test_dynamic_enabled_returns_options(self, context_window_service):
        """Test that options are returned when dynamic is enabled."""
        # Act
        result = context_window_service.get_num_ctx_options(
            context_window=8192,
            dynamic_enabled=True,
            manual_override=False,
        )

        # Assert
        assert result == {"num_ctx": 8192}

    def test_manual_override_returns_options(self, context_window_service):
        """Test that options are returned when manual override is set."""
        # Act
        result = context_window_service.get_num_ctx_options(
            context_window=16384,
            dynamic_enabled=False,
            manual_override=True,
        )

        # Assert
        assert result == {"num_ctx": 16384}

    def test_both_disabled_returns_none(self, context_window_service):
        """Test that None is returned when both dynamic and manual are disabled."""
        # Act
        result = context_window_service.get_num_ctx_options(
            context_window=8192,
            dynamic_enabled=False,
            manual_override=False,
        )

        # Assert
        assert result is None


class TestContextWindowCalculation:
    """Tests for ContextWindowCalculation dataclass."""

    def test_dataclass_creation(self):
        """Test creating a ContextWindowCalculation."""
        # Act
        calc = ContextWindowCalculation(
            current_window=8192,
            reason="initial_setup",
            model_max_context=40960,
            usage_tokens=100,
        )

        # Assert
        assert calc.current_window == 8192
        assert calc.reason == "initial_setup"
        assert calc.model_max_context == 40960
        assert calc.usage_tokens == 100
