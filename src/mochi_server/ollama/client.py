"""Async Ollama client wrapper.

This module provides an async wrapper around the ollama.AsyncClient for
communicating with the Ollama API. All operations are async and the client
is designed to be created once at startup and reused.
"""

import logging
from typing import Any, AsyncIterator

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
            # First get the model from the list to get name and size
            list_response = await self._client.list()
            list_model = None

            if hasattr(list_response, "models"):
                for model_obj in list_response.models:
                    model_obj_name = (
                        model_obj.model
                        if hasattr(model_obj, "model")
                        else model_obj.name
                        if hasattr(model_obj, "name")
                        else None
                    )
                    if model_obj_name == model_name:
                        list_model = model_obj
                        break

            if list_model is None:
                logger.debug(f"Model not found in list: {model_name}")
                return None

            # Get detailed info from show
            show_response = await self._client.show(model_name)
            model_info = ModelInfo.from_ollama_model(
                show_response, list_model=list_model
            )

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

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat responses from Ollama.

        This method sends a chat request to Ollama and yields response chunks
        as they arrive. All chat interactions should use streaming, even for
        non-streaming HTTP endpoints (which collect all chunks before returning).

        Args:
            model: The model name to use for the chat
            messages: List of message dicts in Ollama format:
                      [{"role": "user", "content": "..."}, ...]
            options: Optional model parameters (temperature, etc.)

        Yields:
            dict: Response chunks from Ollama. Each chunk contains:
                  - model: str - The model name
                  - created_at: str - Timestamp
                  - message: dict - Contains role and content
                  - done: bool - True on the final chunk
                  - (final chunk includes eval_count, prompt_eval_count, etc.)

        Raises:
            Exception: If the Ollama API request fails

        Example:
            >>> async for chunk in client.chat_stream(
            ...     model="llama3.2:latest",
            ...     messages=[{"role": "user", "content": "Hello"}]
            ... ):
            ...     if not chunk.get("done"):
            ...         print(chunk["message"]["content"], end="")
        """
        try:
            logger.debug(f"Starting chat stream with model: {model}")
            logger.debug(f"Message count: {len(messages)}")

            # Call Ollama's async chat API with streaming
            async for chunk in await self._client.chat(
                model=model,
                messages=messages,
                stream=True,
                options=options,
            ):
                # Convert the chunk to a dict if it's not already
                if hasattr(chunk, "model_dump"):
                    chunk_dict = chunk.model_dump()
                elif isinstance(chunk, dict):
                    chunk_dict = chunk
                else:
                    # Fallback: convert to dict using vars()
                    chunk_dict = vars(chunk)

                logger.debug(
                    f"Received chunk: done={chunk_dict.get('done')}, "
                    f"content_length={len(chunk_dict.get('message', {}).get('content', ''))}"
                )

                yield chunk_dict

            logger.debug("Chat stream completed")

        except Exception as e:
            logger.error(f"Chat stream failed: {e}")
            raise

    async def close(self) -> None:
        """Close the client and clean up resources.

        This method is provided for completeness but ollama.AsyncClient
        doesn't require explicit cleanup in current versions.
        """
        # ollama.AsyncClient uses httpx internally which handles cleanup
        # This is a placeholder for future cleanup if needed
        logger.debug("OllamaClient closed")
