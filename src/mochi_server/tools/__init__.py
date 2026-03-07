"""Tool discovery, schema conversion, and execution layer.

This package provides functionality for discovering Python functions as tools,
converting them to Ollama-compatible schemas, and executing them during chat.

Modules:
    config: Tool execution policy configuration.
    discovery: ToolDiscoveryService for finding tools in a directory.
    schema: ToolSchemaService for converting functions to Ollama schemas.
    execution: ToolExecutionService for running tools and handling results.
"""

from mochi_server.tools.config import ToolExecutionPolicy, requires_confirmation
from mochi_server.tools.discovery import ToolDiscoveryService
from mochi_server.tools.execution import ToolExecutionResult, ToolExecutionService
from mochi_server.tools.schema import ToolSchemaService

__all__ = [
    "ToolExecutionPolicy",
    "ToolExecutionResult",
    "ToolExecutionService",
    "ToolDiscoveryService",
    "ToolSchemaService",
    "requires_confirmation",
]
