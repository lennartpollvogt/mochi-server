"""FastAPI application factory and lifespan management.

This module contains the create_app() factory function that creates and configures
the FastAPI application instance, including lifespan management for startup/shutdown
and router registration.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mochi_server.config import MochiServerSettings
from mochi_server.ollama import OllamaClient
from mochi_server.routers import chat, health, models, sessions, system_prompts

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for FastAPI application.

    This function handles startup and shutdown logic for the application.
    Expensive objects (like Ollama clients and discovery services) are created
    once at startup and stored in app.state for reuse across all requests.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded while the app is running.
    """
    # Startup: Initialize Ollama client
    settings: MochiServerSettings = app.state.settings
    app.state.ollama_client = OllamaClient(host=settings.ollama_host)
    logger.info(f"Initialized Ollama client with host: {settings.ollama_host}")

    # Check initial connectivity
    connected = await app.state.ollama_client.check_connection()
    if connected:
        logger.info("Successfully connected to Ollama")
    else:
        logger.warning("Could not connect to Ollama - check if server is running")

    yield

    # Shutdown: Clean up resources
    if hasattr(app.state, "ollama_client"):
        await app.state.ollama_client.close()
        logger.info("Ollama client closed")


def create_app(settings: MochiServerSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    This factory function creates a FastAPI instance with all routers,
    middleware, and configuration applied. It can accept an optional
    settings object for testing or explicit configuration.

    Args:
        settings: Optional MochiServerSettings instance. If not provided,
                  settings will be loaded from environment variables.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    if settings is None:
        from mochi_server.dependencies import get_settings

        settings = get_settings()

    app = FastAPI(
        title="mochi-server",
        description="Headless FastAPI server for LLM conversations via Ollama",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings in app.state for lifespan access
    app.state.settings = settings

    # Configure CORS
    # Note: FastAPI's type hints for add_middleware are overly strict
    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(sessions.router)
    app.include_router(chat.router)
    app.include_router(system_prompts.router)

    return app
