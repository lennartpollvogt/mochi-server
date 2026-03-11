"""Pydantic models for tool API requests and responses.

This module defines the request and response schemas for the tools endpoints,
including tool listing, details, reload, and confirmation.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDetails(BaseModel):
    """Detailed information about a single tool."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description from docstring")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters schema",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "add_numbers",
                "description": "Add two numbers together.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "number",
                            "description": "The first number",
                        },
                        "b": {
                            "type": "number",
                            "description": "The second number",
                        },
                    },
                    "required": ["a", "b"],
                },
            }
        }
    )


class ToolListResponse(BaseModel):
    """Response schema for listing all discovered tools."""

    tools: dict[str, ToolDetails] = Field(
        default_factory=dict,
        description="Dictionary of tool names to tool details",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tools": {
                    "add_numbers": {
                        "name": "add_numbers",
                        "description": "Add two numbers together.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "number"},
                                "b": {"type": "number"},
                            },
                            "required": ["a", "b"],
                        },
                    },
                    "multiply_numbers": {
                        "name": "multiply_numbers",
                        "description": "Multiply two numbers together.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "number"},
                                "b": {"type": "number"},
                            },
                            "required": ["a", "b"],
                        },
                    },
                }
            }
        }
    )


class ToolReloadResponse(BaseModel):
    """Response schema for tool reload operation."""

    success: bool = Field(description="Whether reload was successful")
    tools_count: int = Field(description="Number of tools discovered after reload")
    message: str = Field(description="Human-readable message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "tools_count": 5,
                "message": "Successfully reloaded tools",
            }
        }
    )


class ToolConfirmationRequest(BaseModel):
    """Request body for confirming or denying a tool call."""

    confirmation_id: str = Field(
        description="The confirmation ID from the tool_call_confirmation_required event",
    )
    approved: bool = Field(
        description="Whether to approve (true) or deny (false) the tool execution",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confirmation_id": "conf_abc123",
                "approved": True,
            }
        }
    )


class ToolConfirmationResponse(BaseModel):
    """Response schema for tool confirmation."""

    success: bool = Field(description="Whether the confirmation was processed")
    tool_name: str | None = Field(
        default=None,
        description="Name of the tool that was confirmed or denied",
    )
    message: str = Field(description="Human-readable message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "tool_name": "add_numbers",
                "message": "Tool execution approved",
            }
        }
    )
