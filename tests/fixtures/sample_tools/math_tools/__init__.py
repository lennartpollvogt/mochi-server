"""Math tools for testing the tool discovery system.

This module contains math tool functions for testing.
"""

__all__ = ["add_numbers", "multiply_numbers"]


def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The sum of the two numbers
    """
    return a + b


def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The product of the two numbers
    """
    return a * b
