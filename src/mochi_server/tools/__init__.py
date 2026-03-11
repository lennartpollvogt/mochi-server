"""Tool discovery, schema conversion, execution, and policy helpers.

This package provides functionality for discovering Python functions as tools,
converting them to Ollama-compatible schemas, resolving execution policies,
and executing them during chat.

Modules:
    config: Tool execution policy configuration and resolution helpers.
    discovery: ToolDiscoveryService for finding tools in a directory.
    schema: ToolSchemaService for converting functions to Ollama schemas.
    execution: ToolExecutionService for running tools and handling results.
"""

from mochi_server.tools.config import (
    ToolExecutionPolicy,
    normalize_execution_policy,
    requires_confirmation,
    resolve_tool_execution_policy,
    tool_requires_confirmation,
)
from mochi_server.tools.discovery import ToolDiscoveryService
from mochi_server.tools.execution import ToolExecutionResult, ToolExecutionService
from mochi_server.tools.schema import ToolSchemaService

__all__ = [
    "ToolExecutionPolicy",
    "ToolExecutionResult",
    "ToolExecutionService",
    "ToolDiscoveryService",
    "ToolSchemaService",
    "normalize_execution_policy",
    "requires_confirmation",
    "resolve_tool_execution_policy",
    "tool_requires_confirmation",
]
