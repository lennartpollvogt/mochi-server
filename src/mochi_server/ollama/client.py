"""Async Ollama client wrapper.

This module provides an async wrapper around the ollama.AsyncClient for
communicating with the Ollama API. All operations are async and the client
is designed to be created once at startup and reused.
"""

import logging

import ollama

from mochi_server.ollama.types import ModelInfo

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async client for interacting with Ollama API.

    This client wraps ollama.AsyncClient and provides high-level async methods
    for listing models, getting model details, and checking connectivity.
    All chat operations use streaming by default.

    Attributes:
        host: The Ollama server URL (e.g., "http://localhost:11434")
        _client: The underlying ollama.AsyncClient instance
    """

    def __init__(self, host: str) -> None:
        """Initialize the Ollama client.

        Args:
            host: The Ollama server URL
        """
        self.host = host
        self._client = ollama.AsyncClient(host=host)
        logger.info(f"OllamaClient initialized with host: {host}")

    async def check_connection(self) -> bool:
        """Check if the Ollama server is reachable.

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Try to list models as a connectivity check
            await self._client.list()
            logger.debug("Ollama connection check: successful")
            return True
        except Exception as e:
            logger.warning(f"Ollama connection check failed: {e}")
            return False

    async def list_models(self) -> list[ModelInfo]:
        """List all available models that support completion.

        This method fetches all models from Ollama and filters to only include
        models that have "completion" capability. Embedding-only models are excluded.

        Returns:
            list[ModelInfo]: List of available models with their metadata

        Raises:
            Exception: If the Ollama API request fails
        """
        try:
            # Get list of models
            response = await self._client.list()

            # Access models from the response object
            if hasattr(response, "models"):
                models_list = response.models
            else:
                # Fallback for dict-like response
                models_list = response.get("models", [])

            logger.debug(f"Retrieved {len(models_list)} models from Ollama")

            # Fetch detailed info for each model
            model_infos: list[ModelInfo] = []

            for model_obj in models_list:
                # Get model name from the object
                if hasattr(model_obj, "model"):
                    model_name = model_obj.model
                elif hasattr(model_obj, "name"):
                    model_name = model_obj.name
                else:
                    model_name = (
                        model_obj.get("name") if isinstance(model_obj, dict) else None
                    )

                if not model_name:
                    continue

                try:
                    # Get full model details including capabilities
                    show_response = await self._client.show(model_name)

                    # Create ModelInfo from the combined list and show responses
                    # Pass both: model_obj has name/size, show_response has capabilities/context
                    model_info = ModelInfo.from_ollama_model(
                        show_response, list_model=model_obj
                    )

                    # Only include models with completion capability
                    if "completion" in model_info.capabilities:
                        model_infos.append(model_info)
                        logger.debug(f"Added model: {model_name}")
                    else:
                        logger.debug(f"Skipped non-completion model: {model_name}")

                except Exception as e:
                    logger.warning(f"Failed to get details for model {model_name}: {e}")
                    continue

            logger.info(f"Listed {len(model_infos)} completion-capable models")
            return model_infos

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise

    async def get_model_info(self, model_name: str) -> ModelInfo | None:
        """Get detailed information about a specific model.

        Args:
            model_name: Name of the model to query

        Returns:
            ModelInfo | None: Model information if found, None if not found

        Raises:
            Exception: If the Ollama API request fails (except for 404)
        """
        try:
            show_response = await self._client.show(model_name)
            model_info = ModelInfo.from_ollama_model(show_response)

            logger.debug(f"Retrieved info for model: {model_name}")
            return model_info

        except ollama.ResponseError as e:
            if e.status_code == 404:
                logger.debug(f"Model not found: {model_name}")
                return None
            logger.error(f"Ollama API error for model {model_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            raise

    async def close(self) -> None:
        """Close the client and clean up resources.

        This method is provided for completeness but ollama.AsyncClient
        doesn't require explicit cleanup in current versions.
        """
        # ollama.AsyncClient uses httpx internally which handles cleanup
        # This is a placeholder for future cleanup if needed
        logger.debug("OllamaClient closed")
