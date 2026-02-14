"""Models router for listing and retrieving Ollama model information.

This module provides endpoints for querying available models and their details.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from mochi_server.dependencies import get_ollama_client
from mochi_server.models.models import (
    ModelDetail,
    ModelDetailResponse,
    ModelListResponse,
)
from mochi_server.ollama import ModelInfo, OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["models"])


def model_info_to_detail(model_info: ModelInfo) -> ModelDetail:
    """Convert ModelInfo dataclass to ModelDetail Pydantic model.

    Args:
        model_info: The ModelInfo dataclass instance.

    Returns:
        ModelDetail: The Pydantic model for API response.
    """
    return ModelDetail(
        name=model_info.name,
        size_mb=model_info.size_mb,
        format=model_info.format,
        family=model_info.family,
        parameter_size=model_info.parameter_size,
        quantization_level=model_info.quantization_level,
        capabilities=model_info.capabilities,
        context_length=model_info.context_length,
    )


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> ModelListResponse:
    """List all available Ollama models.

    Returns a list of all models that support completion (non-embedding models).
    Each model includes detailed information about size, capabilities, and context length.

    Args:
        ollama_client: The Ollama client (injected).

    Returns:
        ModelListResponse: List of available models with their details.

    Raises:
        HTTPException: If the Ollama API request fails.
    """
    try:
        model_infos = await ollama_client.list_models()
        models = [model_info_to_detail(info) for info in model_infos]

        logger.info(f"Listed {len(models)} models")
        return ModelListResponse(models=models)

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Ollama: {str(e)}",
        )


@router.get("/models/{model_name:path}", response_model=ModelDetailResponse)
async def get_model_detail(
    model_name: str,
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> ModelDetailResponse:
    """Get detailed information about a specific model.

    Args:
        model_name: The name of the model to query (e.g., "qwen3:14b").
        ollama_client: The Ollama client (injected).

    Returns:
        ModelDetailResponse: Detailed information about the model.

    Raises:
        HTTPException: 404 if model not found, 502 if Ollama API fails.
    """
    try:
        model_info = await ollama_client.get_model_info(model_name)

        if model_info is None:
            logger.info(f"Model not found: {model_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model_name}' not found",
            )

        logger.debug(f"Retrieved details for model: {model_name}")
        return ModelDetailResponse(
            name=model_info.name,
            size_mb=model_info.size_mb,
            format=model_info.format,
            family=model_info.family,
            parameter_size=model_info.parameter_size,
            quantization_level=model_info.quantization_level,
            capabilities=model_info.capabilities,
            context_length=model_info.context_length,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Failed to get model details for {model_name}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Ollama: {str(e)}",
        )
