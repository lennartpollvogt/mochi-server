"""Tool discovery service for loading and validating tool modules.

This module provides the ToolDiscoveryService which scans a configured directory
for Python modules containing tool functions, validates them, and exposes them
for use in chat interactions.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ToolDiscoveryService:
    """Service for discovering and loading tools from a directory.

    This service scans a tools directory for Python modules, loads them,
    validates that exported symbols are callable with docstrings, and
    extracts tool groups from __dunder__ variables.
    """

    def __init__(self, tools_dir: Path | None = None):
        """Initialize the ToolDiscoveryService.

        Args:
            tools_dir: Path to the directory containing tool modules.
                      If None, tools will not be discoverable until set.
        """
        self._tools_dir: Path | None = tools_dir
        self._tools: dict[str, Callable[..., Any]] = {}
        self._tool_groups: dict[str, list[str]] = {}
        self._tool_metadata: dict[str, dict[str, Any]] = {}
        self._loaded = False

    @property
    def tools_dir(self) -> Path | None:
        """Get the tools directory path."""
        return self._tools_dir

    @tools_dir.setter
    def tools_dir(self, value: Path | None) -> None:
        """Set the tools directory and trigger reload."""
        self._tools_dir = value
        self._loaded = False
        self._tools.clear()
        self._tool_groups.clear()
        self._tool_metadata.clear()

    def discover_tools(self) -> dict[str, Callable[..., Any]]:
        """Discover all tools from the tools directory.

        Returns:
            Dictionary mapping tool names to callable functions.
        """
        if self._loaded:
            return self._tools

        self._tools = {}
        self._tool_groups = {}
        self._tool_metadata = {}

        if self._tools_dir is None or not self._tools_dir.exists():
            logger.warning(
                f"Tools directory not set or does not exist: {self._tools_dir}"
            )
            self._loaded = True
            return self._tools

        if not self._tools_dir.is_dir():
            logger.warning(f"Tools path is not a directory: {self._tools_dir}")
            self._loaded = True
            return self._tools

        logger.info(f"Discovering tools in: {self._tools_dir}")

        # Scan each subdirectory as a tool module
        for item in self._tools_dir.iterdir():
            if not item.is_dir():
                continue

            # Skip directories starting with underscore
            if item.name.startswith("_"):
                continue

            # Look for __init__.py in the subdirectory
            init_file = item / "__init__.py"
            if not init_file.exists():
                logger.debug(f"Skipping {item.name}: no __init__.py found")
                continue

            # Load the module
            module_tools = self._load_tool_module(item, init_file)
            self._tools.update(module_tools)

        logger.info(f"Discovered {len(self._tools)} tools: {list(self._tools.keys())}")
        self._loaded = True
        return self._tools

    def _load_tool_module(
        self, module_dir: Path, init_file: Path
    ) -> dict[str, Callable[..., Any]]:
        """Load a single tool module and extract tools.

        Args:
            module_dir: Path to the module directory
            init_file: Path to the module's __init__.py

        Returns:
            Dictionary mapping tool names to callable functions
        """
        module_tools = {}
        module_name = module_dir.name

        try:
            # Create a module spec and load the module
            spec = importlib.util.spec_from_file_location(
                f"tools.{module_name}", init_file
            )
            if spec is None or spec.loader is None:
                logger.warning(f"Failed to create spec for {module_name}")
                return module_tools

            module = importlib.util.module_from_spec(spec)

            # Add the module directory to sys.path so it can import dependencies
            parent_dir = str(module_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            spec.loader.exec_module(module)

            # Extract __all__ or use dir() to find exported symbols
            tool_names = getattr(module, "__all__", None)
            if tool_names is None:
                # Fallback to all public symbols that don't start with _
                tool_names = [
                    name
                    for name in dir(module)
                    if not name.startswith("_") and name not in ("typing", "pathlib")
                ]

            # Extract group from __dunder__ variable
            group = getattr(module, "__group__", None)

            # Validate and add each tool
            for name in tool_names:
                if not hasattr(module, name):
                    continue

                attr = getattr(module, name)

                # Must be callable
                if not callable(attr):
                    logger.debug(f"Skipping {name}: not callable")
                    continue

                # Must have a docstring
                if not attr.__doc__:
                    logger.debug(f"Skipping {name}: no docstring")
                    continue

                # Add to tools
                module_tools[name] = attr

                # Track metadata
                self._tool_metadata[name] = {
                    "name": name,
                    "module": module_name,
                    "group": group,
                    "docstring": attr.__doc__,
                }

                # Track group membership
                if group:
                    if group not in self._tool_groups:
                        self._tool_groups[group] = []
                    self._tool_groups[group].append(name)

                logger.debug(f"Discovered tool: {name} (group: {group})")

        except Exception as e:
            logger.error(f"Failed to load tool module {module_name}: {e}")

        return module_tools

    def get_tools(self) -> dict[str, Callable[..., Any]]:
        """Get all discovered tools.

        Returns:
            Dictionary mapping tool names to callable functions.
        """
        if not self._loaded:
            self.discover_tools()
        return self._tools

    def get_tool(self, name: str) -> Callable[..., Any] | None:
        """Get a specific tool by name.

        Args:
            name: The tool name to retrieve.

        Returns:
            The callable tool function, or None if not found.
        """
        if not self._loaded:
            self.discover_tools()
        return self._tools.get(name)

    def get_tool_metadata(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a specific tool.

        Args:
            name: The tool name.

        Returns:
            Dictionary with tool metadata, or None if not found.
        """
        if not self._loaded:
            self.discover_tools()
        return self._tool_metadata.get(name)

    def get_tool_groups(self) -> dict[str, list[str]]:
        """Get all tool groups and their members.

        Returns:
            Dictionary mapping group names to lists of tool names.
        """
        if not self._loaded:
            self.discover_tools()
        return self._tool_groups.copy()

    def get_all_tool_names(self) -> list[str]:
        """Get list of all discovered tool names.

        Returns:
            List of tool names.
        """
        if not self._loaded:
            self.discover_tools()
        return list(self._tools.keys())

    def reload(self) -> None:
        """Force reload of tools from disk."""
        self._loaded = False
        self._tools.clear()
        self._tool_groups.clear()
        self._tool_metadata.clear()
        self.discover_tools()
