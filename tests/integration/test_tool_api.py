"""Integration tests for tool API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from mochi_server import create_app, dependencies
from mochi_server.config import MochiServerSettings
from mochi_server.tools.discovery import ToolDiscoveryService
from mochi_server.tools.schema import ToolSchemaService


class TestToolAPI:
    """Tests for the tool API endpoints."""

    @pytest.fixture
    def tool_settings(self, tmp_path):
        """Create test settings with sample tools directory."""
        fixtures_path = tmp_path / "fixtures" / "sample_tools"
        fixtures_path.mkdir(parents=True)

        math_dir = fixtures_path / "math_tools"
        math_dir.mkdir()
        (math_dir / "__init__.py").write_text(
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

        util_dir = fixtures_path / "utilities"
        util_dir.mkdir()
        (util_dir / "__init__.py").write_text(
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

        return MochiServerSettings(
            host="127.0.0.1",
            port=8000,
            ollama_host="http://localhost:11434",
            data_dir=str(tmp_path),
            sessions_dir="chat_sessions",
            tools_dir=str(fixtures_path),
            agents_dir="agents",
            agent_chats_dir="agents/agent_chats",
            system_prompts_dir="system_prompts",
            log_level="DEBUG",
            cors_origins=["*"],
        )

    @pytest.fixture
    def discovery_service(self, tool_settings):
        """Create a ToolDiscoveryService with the test tools directory."""
        return ToolDiscoveryService(
            tools_dir=tool_settings.resolved_tools_dir,
        )

    @pytest.fixture
    def schema_service(self, discovery_service):
        """Create a ToolSchemaService with discovery service."""
        return ToolSchemaService(discovery_service=discovery_service)

    async def make_request(self, app, method, path):
        """Helper to make async request to app."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with app.router.lifespan_context(app):
                if method == "GET":
                    return await client.get(path)
                if method == "POST":
                    return await client.post(path)
                raise ValueError(f"Unknown method: {method}")

    @pytest.mark.asyncio
    async def test_list_tools_with_tools(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """GET /api/v1/tools returns all discovered tools."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(app, "GET", "/api/v1/tools")

        assert response.status_code == 200
        data = response.json()

        assert "tools" in data
        assert "add_numbers" in data["tools"]
        assert "multiply_numbers" in data["tools"]
        assert "reverse_string" in data["tools"]

    @pytest.mark.asyncio
    async def test_list_tools_empty(self, tmp_path):
        """GET /api/v1/tools with no tools returns empty dict."""
        empty_dir = tmp_path / "empty_tools"
        empty_dir.mkdir()

        settings = MochiServerSettings(
            host="127.0.0.1",
            port=8000,
            ollama_host="http://localhost:11434",
            data_dir=str(tmp_path),
            sessions_dir="chat_sessions",
            tools_dir=str(empty_dir),
            agents_dir="agents",
            agent_chats_dir="agents/agent_chats",
            system_prompts_dir="system_prompts",
            log_level="DEBUG",
            cors_origins=["*"],
        )

        app = create_app(settings=settings)

        response = await self.make_request(app, "GET", "/api/v1/tools")

        assert response.status_code == 200
        data = response.json()
        assert data["tools"] == {}

    @pytest.mark.asyncio
    async def test_list_tools_includes_parameters(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """Verify tool parameters are included in response."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(app, "GET", "/api/v1/tools")

        assert response.status_code == 200
        data = response.json()

        add_numbers_tool = data["tools"]["add_numbers"]
        assert "parameters" in add_numbers_tool
        assert "type" in add_numbers_tool["parameters"]

    @pytest.mark.asyncio
    async def test_get_tool_success(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """GET /api/v1/tools/{name} returns tool details."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(app, "GET", "/api/v1/tools/add_numbers")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "add_numbers"
        assert "description" in data
        assert "parameters" in data
        assert "Add two numbers" in data["description"]

    @pytest.mark.asyncio
    async def test_get_tool_not_found(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """GET /api/v1/tools/{name} returns 404 for non-existent tool."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(
            app,
            "GET",
            "/api/v1/tools/nonexistent_tool",
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_reload_tools_success(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """POST /api/v1/tools/reload returns success."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(app, "POST", "/api/v1/tools/reload")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["tools_count"] == 3

    @pytest.mark.asyncio
    async def test_reload_tools_returns_count(
        self,
        tool_settings,
        discovery_service,
        schema_service,
    ):
        """Verify tools_count in response after reload."""
        discovery_service.discover_tools()

        app = create_app(settings=tool_settings)
        app.dependency_overrides[dependencies.get_tool_discovery_service] = lambda: (
            discovery_service
        )
        app.dependency_overrides[dependencies.get_tool_schema_service] = lambda: (
            schema_service
        )

        response = await self.make_request(app, "POST", "/api/v1/tools/reload")

        assert response.status_code == 200
        data = response.json()

        assert "tools_count" in data
        assert data["tools_count"] == 3
        assert "message" in data
