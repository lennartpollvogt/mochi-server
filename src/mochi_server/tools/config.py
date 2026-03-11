"""Tool execution policy configuration and resolution helpers.

This module defines the supported tool execution policies and provides
helpers for resolving the effective policy for a tool call within a
session's tool settings.
"""

from enum import Enum
from typing import Any


class ToolExecutionPolicy(str, Enum):
    """Policy for tool execution during chat.

    Attributes:
        ALWAYS_CONFIRM: Always require user confirmation before executing a tool.
        NEVER_CONFIRM: Execute the tool automatically without confirmation.
    """

    ALWAYS_CONFIRM = "always_confirm"
    NEVER_CONFIRM = "never_confirm"


# Mapping from policy to whether confirmation is required
CONFIRMATION_REQUIRED = {
    ToolExecutionPolicy.ALWAYS_CONFIRM: True,
    ToolExecutionPolicy.NEVER_CONFIRM: False,
}


def normalize_execution_policy(
    policy: str | ToolExecutionPolicy | None,
) -> ToolExecutionPolicy | None:
    """Normalize a raw policy value to ToolExecutionPolicy.

    Args:
        policy: Raw policy value as a string, enum, or None.

    Returns:
        Normalized ToolExecutionPolicy, or None if the value is invalid.
    """
    if policy is None:
        return None

    if isinstance(policy, ToolExecutionPolicy):
        return policy

    try:
        return ToolExecutionPolicy(policy)
    except ValueError:
        return None


def resolve_tool_execution_policy(
    tool_name: str,
    tool_settings: Any,
) -> ToolExecutionPolicy:
    """Resolve the effective execution policy for a specific tool.

    Resolution order:
    1. Per-tool override in ``tool_settings.tool_policies``
    2. Session default in ``tool_settings.execution_policy``
    3. Safe fallback to ``always_confirm``

    Invalid policy values fall back to ``always_confirm``.

    Args:
        tool_name: The name of the tool being evaluated.
        tool_settings: A tool settings object with ``execution_policy`` and
            optional ``tool_policies`` attributes.

    Returns:
        The effective ToolExecutionPolicy for the tool.
    """
    tool_policies = getattr(tool_settings, "tool_policies", {}) or {}
    override_policy = normalize_execution_policy(tool_policies.get(tool_name))
    if override_policy is not None:
        return override_policy

    default_policy = normalize_execution_policy(
        getattr(tool_settings, "execution_policy", None),
    )
    if default_policy is not None:
        return default_policy

    return ToolExecutionPolicy.ALWAYS_CONFIRM


def requires_confirmation(
    policy: str | ToolExecutionPolicy | None,
) -> bool:
    """Check if an execution policy requires user confirmation.

    Unknown or missing policy values default to requiring confirmation for safety.

    Args:
        policy: The execution policy as a string, enum, or None.

    Returns:
        True if confirmation is required, otherwise False.
    """
    normalized_policy = normalize_execution_policy(policy)
    if normalized_policy is None:
        return True

    return CONFIRMATION_REQUIRED.get(normalized_policy, True)


def tool_requires_confirmation(
    tool_name: str,
    tool_settings: Any,
) -> bool:
    """Check if a specific tool requires confirmation under the given settings.

    Args:
        tool_name: The name of the tool being evaluated.
        tool_settings: A tool settings object with ``execution_policy`` and
            optional ``tool_policies`` attributes.

    Returns:
        True if confirmation is required for the tool, otherwise False.
    """
    effective_policy = resolve_tool_execution_policy(tool_name, tool_settings)
    return requires_confirmation(effective_policy)
