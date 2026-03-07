"""Tool configuration and execution policy.

This module defines the tool execution policy and related configuration
for the tool system.
"""

from enum import Enum


class ToolExecutionPolicy(str, Enum):
    """Policy for tool execution during chat.

    Attributes:
        ALWAYS_CONFIRM: Always require user confirmation before executing tools.
        NEVER_CONFIRM: Always execute tools automatically without confirmation.
        AUTO: Let the model decide (pass tools without confirmation).
    """

    ALWAYS_CONFIRM = "always_confirm"
    NEVER_CONFIRM = "never_confirm"
    AUTO = "auto"


# Mapping from policy to whether confirmation is required
CONFIRMATION_REQUIRED = {
    ToolExecutionPolicy.ALWAYS_CONFIRM: True,
    ToolExecutionPolicy.NEVER_CONFIRM: False,
    ToolExecutionPolicy.AUTO: False,  # Model decides, so we auto-execute
}


def requires_confirmation(policy: str | ToolExecutionPolicy) -> bool:
    """Check if a tool execution policy requires user confirmation.

    Args:
        policy: The execution policy (string or ToolExecutionPolicy enum)

    Returns:
        True if confirmation is required, False otherwise
    """
    if isinstance(policy, str):
        try:
            policy = ToolExecutionPolicy(policy)
        except ValueError:
            # Unknown policy, default to requiring confirmation for safety
            return True

    return CONFIRMATION_REQUIRED.get(policy, True)
