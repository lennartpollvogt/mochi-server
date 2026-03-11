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
    stores basic metadata for discovered tools.
    """

    def __init__(self, tools_dir: Path | None = None):
        """Initialize the ToolDiscoveryService.

        Args:
            tools_dir: Path to the directory containing tool modules.
                If None, tools will not be discoverable until set.
        """
        self._tools_dir: Path | None = tools_dir
        self._tools: dict[str, Callable[..., Any]] = {}
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
        self._tool_metadata.clear()

    def discover_tools(self) -> dict[str, Callable[..., Any]]:
        """Discover all tools from the tools directory.

        Returns:
            Dictionary mapping tool names to callable functions.
        """
        if self._loaded:
            return self._tools

        self._tools = {}
        self._tool_metadata = {}

        if self._tools_dir is None or not self._tools_dir.exists():
            logger.warning(
                "Tools directory not set or does not exist: %s",
                self._tools_dir,
            )
            self._loaded = True
            return self._tools

        if not self._tools_dir.is_dir():
            logger.warning("Tools path is not a directory: %s", self._tools_dir)
            self._loaded = True
            return self._tools

        logger.info("Discovering tools in: %s", self._tools_dir)

        for item in self._tools_dir.iterdir():
            if not item.is_dir():
                continue

            if item.name.startswith("_"):
                continue

            init_file = item / "__init__.py"
            if not init_file.exists():
                logger.debug("Skipping %s: no __init__.py found", item.name)
                continue

            module_tools = self._load_tool_module(item, init_file)
            self._tools.update(module_tools)

        logger.info(
            "Discovered %s tools: %s", len(self._tools), list(self._tools.keys())
        )
        self._loaded = True
        return self._tools

    def _load_tool_module(
        self,
        module_dir: Path,
        init_file: Path,
    ) -> dict[str, Callable[..., Any]]:
        """Load a single tool module and extract tools.

        Args:
            module_dir: Path to the module directory.
            init_file: Path to the module's __init__.py.

        Returns:
            Dictionary mapping tool names to callable functions.
        """
        module_tools: dict[str, Callable[..., Any]] = {}
        module_name = module_dir.name

        try:
            spec = importlib.util.spec_from_file_location(
                f"tools.{module_name}",
                init_file,
            )
            if spec is None or spec.loader is None:
                logger.warning("Failed to create spec for %s", module_name)
                return module_tools

            module = importlib.util.module_from_spec(spec)

            parent_dir = str(module_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            spec.loader.exec_module(module)

            tool_names = getattr(module, "__all__", None)
            if tool_names is None:
                tool_names = [
                    name
                    for name in dir(module)
                    if not name.startswith("_") and name not in ("typing", "pathlib")
                ]

            for name in tool_names:
                if not hasattr(module, name):
                    continue

                attr = getattr(module, name)

                if not callable(attr):
                    logger.debug("Skipping %s: not callable", name)
                    continue

                if not attr.__doc__:
                    logger.debug("Skipping %s: no docstring", name)
                    continue

                module_tools[name] = attr
                self._tool_metadata[name] = {
                    "name": name,
                    "module": module_name,
                    "docstring": attr.__doc__,
                }

                logger.debug("Discovered tool: %s", name)

        except Exception as exc:
            logger.error("Failed to load tool module %s: %s", module_name, exc)

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
        self._tool_metadata.clear()
        self.discover_tools()
