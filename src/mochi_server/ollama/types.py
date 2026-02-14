"""Type definitions for Ollama integration.

This module contains dataclasses and type definitions used for representing
Ollama models and their metadata.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelInfo:
    """Information about an Ollama model.

    This dataclass holds metadata about a model including its name, size,
    format, capabilities, and other relevant information.

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

    name: str
    size_mb: float
    format: str
    family: str
    parameter_size: str
    quantization_level: str
    capabilities: list[str]
    context_length: int

    @staticmethod
    def from_ollama_model(model_data: Any, list_model: Any = None) -> "ModelInfo":
        """Create a ModelInfo instance from Ollama API model data.

        Args:
            model_data: Raw model data from Ollama API (show response)
            list_model: Optional model object from list response (for name/size)

        Returns:
            ModelInfo: Parsed model information
        """

        # Helper to get value from either object attribute or dict key
        def get_value(obj: Any, key: str, default: Any = None) -> Any:
            if hasattr(obj, key):
                return getattr(obj, key, default)
            elif isinstance(obj, dict):
                return obj.get(key, default)
            return default

        # Extract model name (prefer list_model if available)
        if list_model:
            model_name = get_value(list_model, "model") or get_value(
                list_model, "name", "unknown"
            )
        else:
            model_name = get_value(model_data, "model") or get_value(
                model_data, "name", "unknown"
            )

        # Extract size in bytes and convert to MB (prefer list_model if available)
        if list_model:
            size_obj = get_value(list_model, "size", 0)
            # Handle ByteSize object from ollama library
            size_bytes = (
                int(size_obj)
                if hasattr(size_obj, "__int__") or isinstance(size_obj, int)
                else 0
            )
        else:
            size_bytes = get_value(model_data, "size", 0)

        size_mb = round(size_bytes / (1024 * 1024), 1) if size_bytes > 0 else 0.0

        # Extract model details from details dict/object
        details = get_value(model_data, "details", {})
        format_str = get_value(details, "format", "unknown")
        family = get_value(details, "family", "unknown")
        parameter_size = get_value(details, "parameter_size", "unknown")
        quantization_level = get_value(details, "quantization_level", "unknown")

        # Extract capabilities - default to completion if not specified
        capabilities = get_value(model_data, "capabilities", ["completion"])
        if not capabilities:
            capabilities = ["completion"]

        # Extract context length from modelinfo
        modelinfo = get_value(model_data, "modelinfo", {})
        context_length = 2048  # default

        # Try to get context length from family-specific key
        context_key = f"{family}.context_length"
        if isinstance(modelinfo, dict) and context_key in modelinfo:
            context_length = int(modelinfo[context_key])
        elif isinstance(modelinfo, dict) and "context_length" in modelinfo:
            context_length = int(modelinfo["context_length"])
        elif hasattr(modelinfo, context_key.replace(".", "_")):
            context_length = int(
                getattr(modelinfo, context_key.replace(".", "_"), 2048)
            )

        return ModelInfo(
            name=model_name,
            size_mb=size_mb,
            format=format_str,
            family=family,
            parameter_size=parameter_size,
            quantization_level=quantization_level,
            capabilities=capabilities,
            context_length=context_length,
        )
