"""Tool execution service for running tool functions and handling results.

This module provides the ToolExecutionService which executes tool functions,
catches exceptions, and returns results in a standardized format.
"""

import inspect
import logging
import traceback
from dataclasses import dataclass
from typing import Any

from mochi_server.tools.discovery import ToolDiscoveryService

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """Result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully.
        tool_name: Name of the executed tool.
        result: The result string from the tool (or error message).
        error: Error message if execution failed, None otherwise.
    """

    success: bool
    tool_name: str
    result: str
    error: str | None = None


class ToolExecutionService:
    """Service for executing tool functions during chat.

    This service handles tool execution, exception catching, and result
    formatting for LLM consumption.
    """

    def __init__(self, discovery_service: ToolDiscoveryService | None = None):
        """Initialize the ToolExecutionService.

        Args:
            discovery_service: Optional ToolDiscoveryService to get tools from.
        """
        self._discovery_service = discovery_service

    def set_discovery_service(self, discovery_service: ToolDiscoveryService) -> None:
        """Set the tool discovery service.

        Args:
            discovery_service: The ToolDiscoveryService instance.
        """
        self._discovery_service = discovery_service

    def execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute a tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Dictionary of arguments to pass to the tool.

        Returns:
            ToolExecutionResult with success/failure information and result.
        """
        if self._discovery_service is None:
            logger.error("No discovery service set")
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result="",
                error="Tool discovery service not initialized",
            )

        tool_func = self._discovery_service.get_tool(tool_name)
        if tool_func is None:
            logger.warning(f"Tool not found: {tool_name}")
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result="",
                error=f"Tool '{tool_name}' not found",
            )

        # Convert arguments to correct types based on function signature
        converted_args = self._convert_arguments(tool_func, arguments)

        # Execute the tool function
        try:
            logger.info(f"Executing tool {tool_name} with args: {converted_args}")
            result = tool_func(**converted_args)

            # Convert result to string for LLM consumption
            result_str = self._format_result(result)

            logger.info(f"Tool {tool_name} executed successfully")
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                result=result_str,
                error=None,
            )

        except TypeError as e:
            # Wrong number of arguments
            error_msg = f"Invalid arguments for tool '{tool_name}': {str(e)}"
            logger.warning(f"{error_msg}")
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result="",
                error=error_msg,
            )

        except Exception as e:
            # Catch all other exceptions
            error_msg = f"Tool '{tool_name}' raised exception: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result="",
                error=error_msg,
            )

    def _format_result(self, result: Any) -> str:
        """Format a tool result for LLM consumption.

        All results are converted to strings to ensure consistent handling
        by the LLM.

        Args:
            result: The raw result from the tool function.

        Returns:
            String representation of the result.
        """
        if result is None:
            return "Tool executed successfully (no return value)"

        if isinstance(result, str):
            return result

        if isinstance(result, (int, float, bool)):
            return str(result)

        if isinstance(result, (list, tuple)):
            return ", ".join(str(item) for item in result)

        if isinstance(result, dict):
            # Format dict as key-value pairs
            items = [f"{k}: {v}" for k, v in result.items()]
            return ", ".join(items)

        # Fallback: try to convert to string
        try:
            return str(result)
        except Exception:
            return "[Unable to convert result to string]"

    def _convert_arguments(
        self, func: Any, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert arguments to correct types based on function signature.

        Ollama passes all arguments as strings, but the function may expect
        other types (int, float, bool). This method converts them based on
        the function's type annotations.

        Args:
            func: The function to get signature from.
            arguments: The arguments dictionary (may have string values).

        Returns:
            Dictionary with converted argument types.
        """
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            # If we can't get signature, return original arguments
            return arguments

        converted = {}
        for param_name, param in sig.parameters.items():
            if param_name not in arguments:
                continue

            value = arguments[param_name]

            # If already the right type, keep it
            if param.annotation is inspect.Parameter.empty:
                # No annotation, try to infer from default or keep as-is
                converted[param_name] = value
                continue

            # Get the expected type
            expected_type = param.annotation

            # If value is already the correct type, no conversion needed
            if isinstance(value, expected_type):
                converted[param_name] = value
                continue

            # Convert string to expected type
            if isinstance(value, str):
                try:
                    if expected_type is int:
                        converted[param_name] = int(value)
                    elif expected_type is float:
                        converted[param_name] = float(value)
                    elif expected_type is bool:
                        # Handle string booleans
                        if value.lower() in ("true", "1", "yes"):
                            converted[param_name] = True
                        elif value.lower() in ("false", "0", "no"):
                            converted[param_name] = False
                        else:
                            converted[param_name] = bool(value)
                    elif expected_type is str:
                        converted[param_name] = value
                    else:
                        # For other types, try direct conversion
                        converted[param_name] = expected_type(value)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Could not convert '{param_name}' from '{value}' to {expected_type}: {e}"
                    )
                    # Keep original value if conversion fails
                    converted[param_name] = value
            else:
                # Not a string, keep as-is
                converted[param_name] = value

        return converted
