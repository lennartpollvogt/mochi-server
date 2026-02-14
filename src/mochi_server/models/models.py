"""Pydantic models for model API responses.

This module contains request and response schemas for the /api/v1/models endpoints.
"""

from pydantic import BaseModel, Field


class ModelDetail(BaseModel):
    """Detailed information about a single model.

    Attributes:
        name: Full model name (e.g., "qwen3:14b")
        size_mb: Model size in megabytes
        format: Model format (e.g., "gguf")
        family: Model family (e.g., "qwen3")
        parameter_size: Human-readable parameter count (e.g., "14.8B")
        quantization_level: Quantization level (e.g., "Q4_K_M")
        capabilities: List of model capabilities (e.g., ["completion", "tools"])
        context_length: Maximum context window size in tokens
    """

    name: str = Field(..., description="Full model name")
    size_mb: float = Field(..., description="Model size in megabytes")
    format: str = Field(..., description="Model format (e.g., 'gguf')")
    family: str = Field(..., description="Model family name")
    parameter_size: str = Field(..., description="Human-readable parameter count")
    quantization_level: str = Field(..., description="Quantization level")
    capabilities: list[str] = Field(
        ...,
        description="List of model capabilities (e.g., ['completion', 'tools'])",
    )
    context_length: int = Field(
        ..., description="Maximum context window size in tokens"
    )


class ModelListResponse(BaseModel):
    """Response model for listing all available models.

    Attributes:
        models: List of available models with their details
    """

    models: list[ModelDetail] = Field(..., description="List of available models")


class ModelDetailResponse(BaseModel):
    """Response model for getting details of a specific model.

    This is essentially a wrapper around ModelDetail for consistency
    with the API response format, but could be extended in the future
    with additional metadata.

    Attributes:
        All attributes from ModelDetail
    """

    name: str = Field(..., description="Full model name")
    size_mb: float = Field(..., description="Model size in megabytes")
    format: str = Field(..., description="Model format (e.g., 'gguf')")
    family: str = Field(..., description="Model family name")
    parameter_size: str = Field(..., description="Human-readable parameter count")
    quantization_level: str = Field(..., description="Quantization level")
    capabilities: list[str] = Field(
        ...,
        description="List of model capabilities",
    )
    context_length: int = Field(
        ..., description="Maximum context window size in tokens"
    )
