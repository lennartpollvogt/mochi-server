"""Utility tools for testing the tool discovery system.

This module contains utility tool functions for testing.
"""

__all__ = ["reverse_string", "string_length"]

__group__ = "utilities"


def reverse_string(text: str) -> str:
    """Reverse a string.

    Args:
        text: The string to reverse

    Returns:
        The reversed string
    """
    return text[::-1]


def string_length(text: str) -> int:
    """Get the length of a string.

    Args:
        text: The string to measure

    Returns:
        The length of the string
    """
    return len(text)
