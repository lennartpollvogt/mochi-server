"""Dependency injection providers for FastAPI endpoints.

This module provides FastAPI dependency functions that are used across
multiple routers to inject common dependencies like settings and services.
"""

from functools import lru_cache

from mochi_server.config import MochiServerSettings


@lru_cache
def get_settings() -> MochiServerSettings:
    """Get the application settings instance.

    This function is cached so that the same settings instance is reused
    across all requests. Settings are loaded from environment variables
    with the MOCHI_ prefix.

    Returns:
        MochiServerSettings: The application configuration settings.
    """
    return MochiServerSettings()
