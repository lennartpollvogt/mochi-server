"""Dynamic context window management service.

This module provides the DynamicContextWindowService which calculates optimal
context window sizes for each request based on model capabilities and current
token usage.
"""

import logging
from dataclasses import dataclass
from typing import Any

from mochi_server.ollama import OllamaClient

logger = logging.getLogger(__name__)

# Default values for context window management
DEFAULT_INITIAL_WINDOW = 8192
MAX_ADJUSTMENT_HISTORY = 10
SAFE_LIMIT_PERCENTAGE = 0.9  # Use 90% of max context as safe limit
USAGE_THRESHOLD_PERCENTAGE = 0.5  # Ensure 50% buffer above current usage


@dataclass
class ContextWindowCalculation:
    """Result of a context window calculation."""

    current_window: int
    reason: str
    model_max_context: int | None = None
    usage_tokens: int = 0


class DynamicContextWindowService:
    """Service for dynamic context window management.

    This service calculates optimal context window sizes for each request
    based on model capabilities and current token usage. It supports both
    dynamic sizing (automatic adjustments) and manual override modes.

    Attributes:
        ollama_client: The Ollama client for fetching model info
        default_initial_window: Default window size for new conversations
        max_adjustment_history: Maximum number of adjustments to keep in history
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        default_initial_window: int = DEFAULT_INITIAL_WINDOW,
        max_adjustment_history: int = MAX_ADJUSTMENT_HISTORY,
    ) -> None:
        """Initialize the context window service.

        Args:
            ollama_client: The Ollama client for fetching model info
            default_initial_window: Default window size for new conversations
            max_adjustment_history: Maximum number of adjustments to keep in history
        """
        self.ollama_client = ollama_client
        self.default_initial_window = default_initial_window
        self.max_adjustment_history = max_adjustment_history

    async def get_model_max_context(self, model: str) -> int | None:
        """Get the maximum context length for a model.

        Args:
            model: The model name to query

        Returns:
            The maximum context length in tokens, or None if unavailable
        """
        try:
            model_info = await self.ollama_client.get_model_info(model)
            if model_info:
                return model_info.context_length
            return None
        except Exception as e:
            logger.warning(f"Failed to get model info for {model}: {e}")
            return None

    def calculate_context_window(
        self,
        model: str,
        current_window: int,
        dynamic_enabled: bool,
        manual_override: bool,
        model_max_context: int | None,
        usage_tokens: int,
        last_adjustment_reason: str,
    ) -> ContextWindowCalculation:
        """Calculate the optimal context window for a request.

        The calculation follows these rules:
        1. If manual_override is True, keep the current window
        2. If dynamic_enabled is False, keep the current window
        3. For new conversations (usage_tokens == 0), use min(safe_limit, 8192)
        4. For ongoing conversations, ensure at least 50% buffer above usage

        Args:
            model: The model name
            current_window: Current context window size
            dynamic_enabled: Whether dynamic sizing is enabled
            manual_override: Whether user has manually set the window
            model_max_context: Model's maximum context length
            usage_tokens: Current token usage
            last_adjustment_reason: Reason for last adjustment

        Returns:
            ContextWindowCalculation with the calculated window and reason
        """
        # If manual override or dynamic disabled, keep current window
        if manual_override or not dynamic_enabled:
            return ContextWindowCalculation(
                current_window=current_window,
                reason="manual_override" if manual_override else "no_adjustment",
                model_max_context=model_max_context,
                usage_tokens=usage_tokens,
            )

        # Get model's safe limit (90% of max)
        safe_limit = (
            int(model_max_context * SAFE_LIMIT_PERCENTAGE)
            if model_max_context
            else self.default_initial_window
        )

        # For new conversations (no usage yet), use default initial window
        if usage_tokens == 0:
            initial_window = min(safe_limit, self.default_initial_window)
            if current_window != initial_window:
                return ContextWindowCalculation(
                    current_window=initial_window,
                    reason="initial_setup",
                    model_max_context=model_max_context,
                    usage_tokens=usage_tokens,
                )
            return ContextWindowCalculation(
                current_window=current_window,
                reason="no_adjustment",
                model_max_context=model_max_context,
                usage_tokens=usage_tokens,
            )

        # For ongoing conversations, check if we need to adjust
        # Ensure at least 50% buffer above current usage
        required_window = int(usage_tokens / USAGE_THRESHOLD_PERCENTAGE)

        if required_window > current_window:
            # Increase window but don't exceed safe limit
            new_window = min(required_window, safe_limit)
            if new_window != current_window:
                return ContextWindowCalculation(
                    current_window=new_window,
                    reason="usage_threshold",
                    model_max_context=model_max_context,
                    usage_tokens=usage_tokens,
                )

        return ContextWindowCalculation(
            current_window=current_window,
            reason="no_adjustment",
            model_max_context=model_max_context,
            usage_tokens=usage_tokens,
        )

    def get_num_ctx_options(
        self,
        context_window: int,
        dynamic_enabled: bool,
        manual_override: bool,
    ) -> dict[str, Any] | None:
        """Get the options dict to pass to Ollama for context window.

        Args:
            context_window: The calculated context window size
            dynamic_enabled: Whether dynamic sizing is enabled
            manual_override: Whether user has manually set the window

        Returns:
            Options dict with num_ctx if dynamic is enabled or manual override
            is set, None otherwise
        """
        if dynamic_enabled or manual_override:
            return {"num_ctx": context_window}
        return None
