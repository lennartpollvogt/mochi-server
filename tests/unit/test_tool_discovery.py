"""Unit tests for ToolDiscoveryService."""

import pytest

from mochi_server.tools.discovery import ToolDiscoveryService


class TestToolDiscoveryService:
    """Tests for the ToolDiscoveryService class."""

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
__all__ = ["add_numbers", "multiply_numbers"]

def add_numbers(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b

def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b
'''
        )

        # Create utilities subdirectory
        util_dir = tools_dir / "utilities"
        util_dir.mkdir()
        util_init = util_dir / "__init__.py"
        util_init.write_text(
            '''
__all__ = ["reverse_string"]

def reverse_string(text: str) -> str:
    """Reverse a string.

    Args:
        text: String to reverse

    Returns:
        Reversed string
    """
    return text[::-1]
'''
        )

        # Create a directory without __init__.py (should be skipped)
        no_init_dir = tools_dir / "no_init_dir"
        no_init_dir.mkdir()

        # Create a hidden directory (should be skipped)
        hidden_dir = tools_dir / "_hidden"
        hidden_dir.mkdir()
        hidden_init = hidden_dir / "__init__.py"
        hidden_init.write_text(
            '''
__all__ = ["hidden_func"]

def hidden_func() -> str:
    """This should not be discovered."""
    return "hidden"
'''
        )

        return tools_dir

    # 1.1 Basic Discovery

    def test_discover_tools_empty_directory(self, tmp_path):
        """Verify empty dict returned when tools_dir is empty."""
        empty_dir = tmp_path / "empty_tools"
        empty_dir.mkdir()

        service = ToolDiscoveryService(tools_dir=empty_dir)
        tools = service.discover_tools()

        assert tools == {}

    def test_discover_tools_with_subdirectory(self, sample_tools_path):
        """Verify tools found in subdirectory with __init__.py."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        assert "add_numbers" in tools
        assert "multiply_numbers" in tools
        assert "reverse_string" in tools
        assert len(tools) == 3

    def test_discover_tools_multiple_tools(self, sample_tools_path):
        """Verify multiple tools in one module are all discovered."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        assert callable(tools["add_numbers"])
        assert callable(tools["multiply_numbers"])
        assert callable(tools["reverse_string"])

    # 1.2 Directory Filtering

    def test_discover_tools_skips_directories_without_init(self, sample_tools_path):
        """Directories without __init__.py should be skipped."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        assert len(tools) == 3
        assert "no_init_dir" not in tools

    def test_discover_tools_skips_hidden_directories(self, sample_tools_path):
        """Directories starting with _ should be skipped."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        assert "hidden_func" not in tools
        assert len(tools) == 3

    def test_discover_tools_skips_files(self, tmp_path):
        """Files in tools_dir (not directories) should be ignored."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        (tools_dir / "some_file.py").write_text("# some file")

        service = ToolDiscoveryService(tools_dir=tools_dir)
        tools = service.discover_tools()

        assert tools == {}

    # 1.3 Tool Metadata

    def test_get_tool_metadata(self, sample_tools_path):
        """Verify metadata (name, module, docstring) is correct."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        metadata = service.get_tool_metadata("add_numbers")

        assert metadata is not None
        assert metadata["name"] == "add_numbers"
        assert metadata["module"] == "math_tools"
        assert "Add two numbers" in metadata["docstring"]
        assert "group" not in metadata

    def test_get_tool_metadata_not_found(self, sample_tools_path):
        """Verify None returned for non-existent tool."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        metadata = service.get_tool_metadata("nonexistent_tool")

        assert metadata is None

    # 1.4 Tool Retrieval

    def test_get_tool(self, sample_tools_path):
        """Verify correct callable is returned."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        tool = service.get_tool("add_numbers")

        assert callable(tool)
        assert tool(2, 3) == 5

    def test_get_tool_not_found(self, sample_tools_path):
        """Verify None for non-existent tool."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        tool = service.get_tool("nonexistent_tool")

        assert tool is None

    def test_get_all_tool_names(self, sample_tools_path):
        """Verify list of all tool names."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        names = service.get_all_tool_names()

        assert "add_numbers" in names
        assert "multiply_numbers" in names
        assert "reverse_string" in names
        assert len(names) == 3

    # 1.5 Reload Functionality

    def test_reload(self, sample_tools_path):
        """Verify reload clears and re-discovers tools."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        initial_tools = service.get_all_tool_names()
        assert len(initial_tools) == 3

        new_dir = sample_tools_path / "new_tools"
        new_dir.mkdir()
        (new_dir / "__init__.py").write_text(
            '''
__all__ = ["new_tool"]

def new_tool() -> str:
    """A new tool."""
    return "new"
'''
        )

        service.reload()

        reloaded_tools = service.get_all_tool_names()
        assert "new_tool" in reloaded_tools
        assert len(reloaded_tools) == 4

    def test_tools_dir_setter_triggers_reload(self, sample_tools_path):
        """Verify setting tools_dir triggers discovery."""
        service = ToolDiscoveryService(tools_dir=None)
        assert service.get_all_tool_names() == []

        service.tools_dir = sample_tools_path

        tools = service.get_all_tool_names()
        assert len(tools) == 3

    def test_discover_tools_nonexistent_dir(self, tmp_path):
        """Verify empty dict when tools_dir doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent"

        service = ToolDiscoveryService(tools_dir=nonexistent_dir)
        tools = service.discover_tools()

        assert tools == {}

    def test_discover_tools_not_a_directory(self, tmp_path):
        """Verify empty dict when tools_path is not a directory."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("not a directory")

        service = ToolDiscoveryService(tools_dir=file_path)
        tools = service.discover_tools()

        assert tools == {}

    # 1.6 Export Validation

    def test_discover_tools_skips_non_callable_exports(self, tmp_path):
        """Non-callable names in __all__ should be skipped."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        bad_dir = tools_dir / "bad_exports"
        bad_dir.mkdir()
        (bad_dir / "__init__.py").write_text(
            '''
__all__ = ["valid_tool", "not_a_function"]

not_a_function = 42

def valid_tool() -> str:
    """A valid tool."""
    return "ok"
'''
        )

        service = ToolDiscoveryService(tools_dir=tools_dir)
        tools = service.discover_tools()

        assert "valid_tool" in tools
        assert "not_a_function" not in tools

    def test_discover_tools_skips_exports_without_docstring(self, tmp_path):
        """Callable exports without docstrings should be skipped."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        no_doc_dir = tools_dir / "no_doc_tools"
        no_doc_dir.mkdir()
        (no_doc_dir / "__init__.py").write_text(
            '''
__all__ = ["documented_tool", "undocumented_tool"]

def documented_tool() -> str:
    """A documented tool."""
    return "ok"

def undocumented_tool() -> str:
    return "missing docstring"
'''
        )

        service = ToolDiscoveryService(tools_dir=tools_dir)
        tools = service.discover_tools()

        assert "documented_tool" in tools
        assert "undocumented_tool" not in tools

    def test_discover_tools_falls_back_to_public_symbols_without_all(self, tmp_path):
        """Public callables should be discovered when __all__ is missing."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        fallback_dir = tools_dir / "fallback_tools"
        fallback_dir.mkdir()
        (fallback_dir / "__init__.py").write_text(
            '''
def public_tool() -> str:
    """A public tool."""
    return "public"

def another_tool() -> str:
    """Another public tool."""
    return "another"

def _private_tool() -> str:
    """A private tool."""
    return "private"
'''
        )

        service = ToolDiscoveryService(tools_dir=tools_dir)
        tools = service.discover_tools()

        assert "public_tool" in tools
        assert "another_tool" in tools
        assert "_private_tool" not in tools
