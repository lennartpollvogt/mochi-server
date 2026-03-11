"""Unit tests for ToolExecutionService."""

import pytest

from mochi_server.tools.discovery import ToolDiscoveryService
from mochi_server.tools.execution import ToolExecutionResult, ToolExecutionService


class TestToolExecutionService:
    """Tests for the ToolExecutionService class."""

    @pytest.fixture
    def sample_tools_path(self, tmp_path):
        """Create a sample tools directory structure for testing."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create math_tools subdirectory
        math_dir = tools_dir / "math_tools"
        math_dir.mkdir()
        math_init = math_dir / "__init__.py"
        math_init.write_text(
            '''
__all__ = ["add_numbers", "multiply_numbers", "error_tool", "return_none_tool"]

def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The sum of the two numbers
    """
    return a + b

def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The product of the two numbers
    """
    return a * b

def error_tool() -> str:
    """A tool that raises an exception."""
    raise ValueError("This is an error")

def return_none_tool() -> None:
    """A tool that returns None."""
    return None
'''
        )

        return tools_dir

    @pytest.fixture
    def discovery_service(self, sample_tools_path):
        """Create a ToolDiscoveryService with sample tools."""
        return ToolDiscoveryService(tools_dir=sample_tools_path)

    @pytest.fixture
    def execution_service(self, discovery_service):
        """Create a ToolExecutionService with discovery service."""
        return ToolExecutionService(discovery_service=discovery_service)

    # 3.1 Basic Execution

    def test_execute_tool_success(self, execution_service):
        """Verify tool executes with correct arguments."""
        result = execution_service.execute_tool("add_numbers", {"a": 2, "b": 3})

        assert result.success is True
        assert result.tool_name == "add_numbers"
        assert result.error is None

    def test_execute_tool_returns_result(self, execution_service):
        """Verify result is correctly returned as string."""
        result = execution_service.execute_tool("add_numbers", {"a": 2, "b": 3})

        assert result.success is True
        assert result.result == "5"

    def test_execute_tool_not_found(self, execution_service):
        """Verify error returned for non-existent tool."""
        result = execution_service.execute_tool("nonexistent_tool", {})

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    # 3.2 Error Handling

    def test_execute_tool_type_error(self, execution_service):
        """Verify TypeError handled gracefully (wrong args)."""
        # Try to call add_numbers with wrong number of arguments
        result = execution_service.execute_tool("add_numbers", {"a": 2})

        assert result.success is False
        assert result.error is not None

    def test_execute_tool_runtime_error(self, execution_service):
        """Verify runtime exceptions are caught and returned as errors."""
        result = execution_service.execute_tool("error_tool", {})

        assert result.success is False
        assert result.error is not None
        # The error message contains the exception info
        assert "exception" in result.error.lower()

    def test_execute_tool_no_discovery_service(self):
        """Verify error when no discovery service set."""
        service = ToolExecutionService(discovery_service=None)
        result = service.execute_tool("some_tool", {})

        assert result.success is False
        assert result.error is not None
        assert "not initialized" in result.error

    # 3.3 Result Formatting - using existing fixture tools

    def test_result_int_converted_to_string(self, execution_service):
        """Verify int is converted to string."""
        result = execution_service.execute_tool("add_numbers", {"a": 5, "b": 10})

        assert result.success is True
        assert result.result == "15"

    def test_result_none_converted_to_string(self, execution_service):
        """Verify None return value is converted to string."""
        result = execution_service.execute_tool("return_none_tool", {})

        assert result.success is True
        assert result.result is not None
        assert "no return value" in result.result.lower()

    # 3.4 Execution Result

    def test_execution_result_success(self, execution_service):
        """Verify success=True for successful execution."""
        result = execution_service.execute_tool("add_numbers", {"a": 1, "b": 2})

        assert result.success is True
        assert result.error is None

    def test_execution_result_error(self, execution_service):
        """Verify success=False and error message set on failure."""
        result = execution_service.execute_tool("nonexistent", {})

        assert result.success is False
        assert result.error is not None

    def test_execution_result_dataclass_fields(self, execution_service):
        """Verify ToolExecutionResult has correct fields."""
        result = execution_service.execute_tool("add_numbers", {"a": 1, "b": 2})

        assert hasattr(result, "success")
        assert hasattr(result, "tool_name")
        assert hasattr(result, "result")
        assert hasattr(result, "error")


class TestToolExecutionResult:
    """Tests for the ToolExecutionResult dataclass."""

    def test_dataclass_creation_success(self):
        """Test creating a success result."""
        result = ToolExecutionResult(
            success=True,
            tool_name="test_tool",
            result="test result",
            error=None,
        )

        assert result.success is True
        assert result.tool_name == "test_tool"
        assert result.result == "test result"
        assert result.error is None

    def test_dataclass_creation_error(self):
        """Test creating an error result."""
        result = ToolExecutionResult(
            success=False,
            tool_name="test_tool",
            result="",
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


class TestToolExecutionResultFormatting:
    """Tests for result formatting in ToolExecutionService."""

    @pytest.fixture
    def service(self):
        """Create a service with mocked tool functions."""
        discovery_service = ToolDiscoveryService(tools_dir=None)

        # Add test tools directly to the internal dict
        discovery_service._tools = {
            "list_tool": lambda: [1, 2, 3],
            "dict_tool": lambda: {"a": 1, "b": 2},
            "float_tool": lambda: 3.14,
            "bool_tool": lambda: True,
            "string_tool": lambda: "hello",
        }
        discovery_service._tool_metadata = {
            name: {
                "name": name,
                "module": "test",
                "docstring": f"Test tool {name}",
            }
            for name in discovery_service._tools
        }
        discovery_service._loaded = True

        execution_service = ToolExecutionService(discovery_service=discovery_service)
        return execution_service

    def test_list_result_formatted(self, service):
        """Verify list result is formatted as comma-separated string."""
        result = service.execute_tool("list_tool", {})

        assert result.success is True
        assert "1" in result.result
        assert "2" in result.result
        assert "3" in result.result

    def test_dict_result_formatted(self, service):
        """Verify dict result is formatted as key-value pairs."""
        result = service.execute_tool("dict_tool", {})

        assert result.success is True
        assert "a: 1" in result.result
        assert "b: 2" in result.result

    def test_float_result_formatted(self, service):
        """Verify float result is converted to string."""
        result = service.execute_tool("float_tool", {})

        assert result.success is True
        assert "3.14" in result.result

    def test_bool_result_formatted(self, service):
        """Verify bool result is converted to string."""
        result = service.execute_tool("bool_tool", {})

        assert result.success is True
        assert result.result == "True"

    def test_string_result_unchanged(self, service):
        """Verify string result remains unchanged."""
        result = service.execute_tool("string_tool", {})

        assert result.success is True
        assert result.result == "hello"
