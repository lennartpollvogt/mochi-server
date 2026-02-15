"""FastAPI routers for API endpoints.

This package contains all route handlers organized by resource type.
Each router module defines endpoints for a specific domain (health, sessions, chat, etc.).
"""

from mochi_server.routers import system_prompts

__all__ = [
    "system_prompts",
]
