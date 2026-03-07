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
__group__ = "math"

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
__group__ = "utilities"

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

        # Should find tools from both subdirectories
        assert "add_numbers" in tools
        assert "multiply_numbers" in tools
        assert "reverse_string" in tools
        assert len(tools) == 3

    def test_discover_tools_multiple_tools(self, sample_tools_path):
        """Verify multiple tools in one module are all discovered."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        # math_tools should have 2 tools
        assert callable(tools["add_numbers"])
        assert callable(tools["multiply_numbers"])
        assert callable(tools["reverse_string"])

    # 1.2 Directory Filtering

    def test_discover_tools_skips_directories_without_init(self, sample_tools_path):
        """Directories without __init__.py should be skipped."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        # no_init_dir should not be discovered
        assert len(tools) == 3
        assert "no_init_dir" not in tools

    def test_discover_tools_skips_hidden_directories(self, sample_tools_path):
        """Directories starting with _ should be skipped."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        tools = service.discover_tools()

        # _hidden should not be discovered
        assert "hidden_func" not in tools
        assert len(tools) == 3

    def test_discover_tools_skips_files(self, tmp_path):
        """Files in tools_dir (not directories) should be ignored."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create a file (not a directory)
        (tools_dir / "some_file.py").write_text("# some file")

        service = ToolDiscoveryService(tools_dir=tools_dir)
        tools = service.discover_tools()

        assert tools == {}

    # 1.3 Tool Groups

    def test_discover_tools_extracts_groups(self, sample_tools_path):
        """Verify __group__ variable is correctly extracted."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        groups = service.get_tool_groups()

        assert "math" in groups
        assert "utilities" in groups

    def test_discover_tools_multiple_groups(self, sample_tools_path):
        """Verify multiple groups are tracked separately."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        groups = service.get_tool_groups()

        assert "add_numbers" in groups["math"]
        assert "multiply_numbers" in groups["math"]
        assert "reverse_string" in groups["utilities"]

    def test_discover_tools_no_group(self, tmp_path):
        """Tools without __group__ should not appear in groups."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        no_group_dir = tools_dir / "no_group_tools"
        no_group_dir.mkdir()
        (no_group_dir / "__init__.py").write_text(
            '''
__all__ = ["some_func"]

def some_func() -> str:
    """A function without group."""
    return "test"
'''
        )

        service = ToolDiscoveryService(tools_dir=tools_dir)
        service.discover_tools()

        groups = service.get_tool_groups()
        # Should have empty groups dict or not include no_group_tools
        assert "no_group_tools" not in groups

    # 1.4 Tool Metadata

    def test_get_tool_metadata(self, sample_tools_path):
        """Verify metadata (name, module, group, docstring) is correct."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        metadata = service.get_tool_metadata("add_numbers")

        assert metadata is not None
        assert metadata["name"] == "add_numbers"
        assert metadata["module"] == "math_tools"
        assert metadata["group"] == "math"
        assert "Add two numbers" in metadata["docstring"]

    def test_get_tool_metadata_not_found(self, sample_tools_path):
        """Verify None returned for non-existent tool."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        metadata = service.get_tool_metadata("nonexistent_tool")

        assert metadata is None

    # 1.5 Tool Retrieval

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

    # 1.6 Reload Functionality

    def test_reload(self, sample_tools_path):
        """Verify reload clears and re-discovers tools."""
        service = ToolDiscoveryService(tools_dir=sample_tools_path)
        service.discover_tools()

        initial_tools = service.get_all_tool_names()
        assert len(initial_tools) == 3

        # Modify the tools directory
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

        # Reload
        service.reload()

        reloaded_tools = service.get_all_tool_names()
        # Should now include the new tool
        assert "new_tool" in reloaded_tools
        assert len(reloaded_tools) == 4

    def test_tools_dir_setter_triggers_reload(self, sample_tools_path):
        """Verify setting tools_dir triggers discovery."""
        service = ToolDiscoveryService(tools_dir=None)
        assert service.get_all_tool_names() == []

        # Set tools_dir
        service.tools_dir = sample_tools_path

        # Should have discovered tools
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
