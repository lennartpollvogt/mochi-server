"""Unit tests for ToolSchemaService."""

from unittest.mock import patch

import pytest

from mochi_server.tools.discovery import ToolDiscoveryService
from mochi_server.tools.schema import ToolSchemaService


class TestToolSchemaService:
    """Tests for the ToolSchemaService class."""

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
__all__ = ["add_numbers"]

def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The sum of the two numbers
    """
    return a + b
'''
        )

        return tools_dir

    @pytest.fixture
    def discovery_service(self, sample_tools_path):
        """Create a ToolDiscoveryService with sample tools."""
        return ToolDiscoveryService(tools_dir=sample_tools_path)

    @pytest.fixture
    def schema_service(self, discovery_service):
        """Create a ToolSchemaService with discovery service."""
        service = ToolSchemaService(discovery_service=discovery_service)
        return service

    # 2.1 Schema Generation

    def test_get_tool_schema(self, schema_service):
        """Verify schema is generated for a tool."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None

    def test_get_tool_schema_not_found(self, schema_service):
        """Verify None for non-existent tool."""
        schema = schema_service.get_tool_schema("nonexistent_tool")

        assert schema is None

    def test_get_all_tool_schemas(self, schema_service):
        """Verify all tool schemas are returned."""
        schemas = schema_service.get_all_tool_schemas()

        assert "add_numbers" in schemas
        assert len(schemas) == 1

    def test_get_tool_schema_no_discovery_service(self):
        """Verify None when no discovery service is set."""
        service = ToolSchemaService(discovery_service=None)
        schema = service.get_tool_schema("some_tool")

        assert schema is None

    # 2.2 Schema Format

    def test_schema_has_type_function(self, schema_service):
        """Verify schema has 'type': 'function'."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None
        assert schema.get("type") == "function"

    def test_schema_has_function_name(self, schema_service):
        """Verify function name is present."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None
        assert "function" in schema
        assert schema["function"].get("name") == "add_numbers"

    def test_schema_has_function_description(self, schema_service):
        """Verify description is extracted from docstring."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None
        assert "function" in schema
        description = schema["function"].get("description", "")
        assert "Add two numbers" in description

    def test_schema_has_parameters(self, schema_service):
        """Verify parameters object is present."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None
        assert "function" in schema
        assert "parameters" in schema["function"]

    def test_schema_has_required(self, schema_service):
        """Verify required array matches function signature."""
        schema = schema_service.get_tool_schema("add_numbers")

        assert schema is not None
        assert "function" in schema
        params = schema["function"].get("parameters", {})
        required = params.get("required", [])

        # Both a and b have no defaults, so should be required
        assert "a" in required
        assert "b" in required

    # 2.3 Schema Caching

    def test_schema_is_cached(self, schema_service):
        """Verify same schema returned on subsequent calls."""
        schema1 = schema_service.get_tool_schema("add_numbers")
        schema2 = schema_service.get_tool_schema("add_numbers")

        assert schema1 is schema2

    def test_invalidate_cache(self, schema_service):
        """Verify cache can be invalidated."""
        schema1 = schema_service.get_tool_schema("add_numbers")

        # Invalidate cache
        schema_service.invalidate_cache("add_numbers")

        schema2 = schema_service.get_tool_schema("add_numbers")

        # Should be different objects (new schema generated)
        assert schema1 is not schema2

    def test_invalidate_all_cache(self, schema_service):
        """Verify all cache can be invalidated."""
        schema1 = schema_service.get_tool_schema("add_numbers")

        # Invalidate all cache
        schema_service.invalidate_cache()

        schema2 = schema_service.get_tool_schema("add_numbers")

        # Should be different objects (new schema generated)
        assert schema1 is not schema2

    def test_cache_cleared_on_reload(self, schema_service, sample_tools_path):
        """Verify cache cleared when explicitly invalidated after discovery reloads."""
        schema1 = schema_service.get_tool_schema("add_numbers")

        # Get the discovery service and reload
        discovery_service = schema_service._discovery_service
        discovery_service.reload()

        # The schema service cache must be explicitly invalidated after discovery reloads
        # This is how the implementation works - see routers/tools.py reload endpoint
        schema_service.invalidate_cache()

        schema2 = schema_service.get_tool_schema("add_numbers")

        # Should be different objects after explicit cache invalidation
        assert schema1 is not schema2

    # 2.4 Fallback Handling

    def test_fallback_when_ollama_utils_unavailable(self, discovery_service):
        """Verify manual schema generation works as fallback."""
        with patch("mochi_server.tools.schema.HAS_OLLAMA_UTILS", False):
            service = ToolSchemaService(discovery_service=discovery_service)
            schema = service.get_tool_schema("add_numbers")

            assert schema is not None
            assert schema.get("type") == "function"
            assert "function" in schema
            assert schema["function"]["name"] == "add_numbers"

    def test_schema_with_no_discovery_service_set(self):
        """Verify schema returns None when discovery service not set."""
        service = ToolSchemaService(discovery_service=None)

        # This should return None since there's no discovery service
        result = service.get_tool_schema("any_tool")

        assert result is None

    def test_get_all_schemas_with_no_discovery_service(self):
        """Verify get_all_tool_schemas returns empty dict when no discovery service."""
        service = ToolSchemaService(discovery_service=None)

        result = service.get_all_tool_schemas()

        assert result == {}
