"""Dependency injection providers for FastAPI endpoints.

This module provides FastAPI dependency functions that are used across
multiple routers to inject common dependencies like settings and services.
"""

from functools import lru_cache

from fastapi import HTTPException, Request

from mochi_server.config import MochiServerSettings
from mochi_server.ollama import OllamaClient
from mochi_server.sessions import SessionManager


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


def get_ollama_client(request: Request) -> OllamaClient:
    """Get the Ollama client from app state.

    This function retrieves the OllamaClient instance that was created
    during application startup and stored in app.state.

    Args:
        request: The FastAPI request object.

    Returns:
        OllamaClient: The Ollama client instance.

    Raises:
        HTTPException: If the Ollama client is not initialized (503 Service Unavailable).
    """
    if not hasattr(request.app.state, "ollama_client"):
        raise HTTPException(
            status_code=503,
            detail="Ollama client not initialized",
        )
    return request.app.state.ollama_client


def get_session_manager(request: Request) -> SessionManager:
    """Get a SessionManager instance with app configuration.

    Creates a new SessionManager for each request, using the sessions
    directory from settings and the Ollama client from app state.

    Args:
        request: The FastAPI request object.

    Returns:
        SessionManager: A new SessionManager instance.

    Raises:
        HTTPException: If the Ollama client is not initialized (503 Service Unavailable).
    """
    # Use settings from app.state instead of cached get_settings()
    # This ensures tests can use their own isolated settings
    settings = request.app.state.settings
    ollama_client = get_ollama_client(request)

    return SessionManager(
        sessions_dir=settings.resolved_sessions_dir,
        ollama_client=ollama_client,
    )
