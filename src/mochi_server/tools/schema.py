"""Tool schema service for converting Python functions to Ollama tool format.

This module provides the ToolSchemaService which converts Python functions
into Ollama-compatible tool schemas using the ollama SDK's built-in conversion.
"""

import inspect
import logging
from typing import Any

from mochi_server.tools.discovery import ToolDiscoveryService

logger = logging.getLogger(__name__)

# Import the Ollama utility for converting functions to tools
# This is the recommended way according to Ollama documentation
try:
    from ollama import _utils

    HAS_OLLAMA_UTILS = True
except ImportError:
    HAS_OLLAMA_UTILS = False
    logger.warning("Could not import ollama._utils, schema conversion may be limited")


class ToolSchemaService:
    """Service for converting Python functions to Ollama tool schemas.

    This service uses the Ollama SDK's built-in function-to-tool conversion
    to generate valid tool schemas for the Ollama chat API.
    """

    def __init__(self, discovery_service: ToolDiscoveryService | None = None):
        """Initialize the ToolSchemaService.

        Args:
            discovery_service: Optional ToolDiscoveryService to get tools from.
        """
        self._discovery_service = discovery_service
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def set_discovery_service(self, discovery_service: ToolDiscoveryService) -> None:
        """Set the tool discovery service.

        Args:
            discovery_service: The ToolDiscoveryService instance.
        """
        self._discovery_service = discovery_service
        # Invalidate cache when discovery service changes
        self._schema_cache.clear()

    def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Get the Ollama tool schema for a specific tool.

        Args:
            tool_name: The name of the tool.

        Returns:
            Ollama-compatible tool schema dict, or None if tool not found.
        """
        if tool_name in self._schema_cache:
            return self._schema_cache[tool_name]

        if self._discovery_service is None:
            logger.warning("No discovery service set")
            return None

        tool_func = self._discovery_service.get_tool(tool_name)
        if tool_func is None:
            logger.warning(f"Tool not found: {tool_name}")
            return None

        schema = self._convert_function_to_tool_schema(tool_func, tool_name)
        if schema:
            self._schema_cache[tool_name] = schema

        return schema

    def get_all_tool_schemas(self) -> dict[str, dict[str, Any]]:
        """Get Ollama tool schemas for all discovered tools.

        Returns:
            Dictionary mapping tool names to their Ollama tool schemas.
        """
        schemas = {}

        if self._discovery_service is None:
            logger.warning("No discovery service set")
            return schemas

        tools = self._discovery_service.get_tools()
        for tool_name in tools:
            schema = self.get_tool_schema(tool_name)
            if schema:
                schemas[tool_name] = schema

        return schemas

    def _convert_function_to_tool_schema(
        self, func: Any, tool_name: str
    ) -> dict[str, Any] | None:
        """Convert a Python function to Ollama tool schema format.

        Args:
            func: The Python function to convert.
            tool_name: The name of the tool.

        Returns:
            Ollama-compatible tool schema, or None if conversion fails.
        """
        if not HAS_OLLAMA_UTILS:
            # Fallback: manually construct schema from docstring
            return self._manual_schema_from_docstring(func, tool_name)

        try:
            # Use Ollama's built-in conversion
            tool_schema = _utils.convert_function_to_tool(func)
            # Convert Tool object to dict
            if hasattr(tool_schema, "model_dump"):
                return tool_schema.model_dump()
            return tool_schema
        except Exception as e:
            logger.error(f"Failed to convert function {tool_name}: {e}")
            # Fallback to manual schema
            return self._manual_schema_from_docstring(func, tool_name)

    def _manual_schema_from_docstring(
        self, func: Any, tool_name: str
    ) -> dict[str, Any] | None:
        """Manually construct tool schema from function docstring.

        This is a fallback when ollama._utils is not available.

        Args:
            func: The Python function.
            tool_name: The name of the tool.

        Returns:
            Basic Ollama-compatible tool schema.
        """
        docstring = func.__doc__ or "No description available"

        # Try to extract parameters from function signature
        try:
            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                properties[param_name] = {
                    "type": "string",  # Default to string
                    "description": f"Parameter {param_name}",
                }
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            return {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": docstring.split("\n")[0].strip(),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        except Exception as e:
            logger.error(f"Failed to parse function signature for {tool_name}: {e}")
            return {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": docstring,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }

    def invalidate_cache(self, tool_name: str | None = None) -> None:
        """Invalidate the schema cache.

        Args:
            tool_name: Specific tool to invalidate, or None to clear all.
        """
        if tool_name:
            self._schema_cache.pop(tool_name, None)
        else:
            self._schema_cache.clear()
