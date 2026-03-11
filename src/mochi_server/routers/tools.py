"""Tools API endpoints.

This module provides endpoints for discovering, listing, and reloading tools.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from mochi_server.dependencies import (
    get_tool_discovery_service,
    get_tool_schema_service,
)
from mochi_server.models.tools import (
    ToolDetails,
    ToolListResponse,
    ToolReloadResponse,
)
from mochi_server.tools import ToolDiscoveryService, ToolSchemaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("", response_model=ToolListResponse, summary="List all tools")
async def list_tools(
    discovery_service: Annotated[
        ToolDiscoveryService, Depends(get_tool_discovery_service)
    ],
    schema_service: Annotated[ToolSchemaService, Depends(get_tool_schema_service)],
) -> ToolListResponse:
    """List all discovered tools.

    Returns:
        ToolListResponse with all discovered tools

    Example:
        GET /api/v1/tools
        {
            "tools": {
                "add_numbers": {
                    "name": "add_numbers",
                    "description": "Add two numbers together.",
                    "parameters": {...}
                }
            }
        }
    """
    discovery_service.discover_tools()

    schemas = schema_service.get_all_tool_schemas()

    tools = {}
    for tool_name, schema in schemas.items():
        metadata = discovery_service.get_tool_metadata(tool_name)
        description = metadata.get("docstring", "") if metadata else ""

        parameters = {}
        if "function" in schema:
            parameters = schema["function"].get("parameters", {})

        tools[tool_name] = ToolDetails(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

    return ToolListResponse(tools=tools)


@router.get(
    "/{tool_name}",
    response_model=ToolDetails,
    summary="Get tool details",
)
async def get_tool(
    tool_name: str,
    discovery_service: Annotated[
        ToolDiscoveryService, Depends(get_tool_discovery_service)
    ],
    schema_service: Annotated[ToolSchemaService, Depends(get_tool_schema_service)],
) -> ToolDetails:
    """Get detailed information about a specific tool.

    Args:
        tool_name: The name of the tool to retrieve

    Returns:
        ToolDetails with tool information

    Raises:
        HTTPException: 404 if tool not found
    """
    discovery_service.discover_tools()

    tool_func = discovery_service.get_tool(tool_name)
    if tool_func is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "tool_not_found",
                    "message": f"Tool '{tool_name}' not found",
                    "details": {"tool_name": tool_name},
                }
            },
        )

    metadata = discovery_service.get_tool_metadata(tool_name)
    description = metadata.get("docstring", "") if metadata else ""

    schema = schema_service.get_tool_schema(tool_name)
    parameters = {}
    if schema and "function" in schema:
        parameters = schema["function"].get("parameters", {})

    return ToolDetails(
        name=tool_name,
        description=description,
        parameters=parameters,
    )


@router.post(
    "/reload",
    response_model=ToolReloadResponse,
    summary="Reload tools from disk",
)
async def reload_tools(
    discovery_service: Annotated[
        ToolDiscoveryService, Depends(get_tool_discovery_service)
    ],
    schema_service: Annotated[ToolSchemaService, Depends(get_tool_schema_service)],
) -> ToolReloadResponse:
    """Force reload all tools from the tools directory.

    This endpoint clears the tool cache and re-discovers all tools from disk.
    Useful when you've added or removed tools while the server is running.

    Returns:
        ToolReloadResponse with reload status

    Example:
        POST /api/v1/tools/reload
        {
            "success": true,
            "tools_count": 5,
            "message": "Successfully reloaded tools"
        }
    """
    logger.info("Reloading tools from disk")

    schema_service.invalidate_cache()
    discovery_service.reload()

    tools = discovery_service.get_tools()
    tools_count = len(tools)

    logger.info("Reloaded %s tools", tools_count)

    return ToolReloadResponse(
        success=True,
        tools_count=tools_count,
        message=f"Successfully reloaded {tools_count} tools",
    )
