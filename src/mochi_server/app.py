"""FastAPI application factory and lifespan management.

This module contains the create_app() factory function that creates and configures
the FastAPI application instance, including lifespan management for startup/shutdown
and router registration.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mochi_server.config import MochiServerSettings
from mochi_server.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for FastAPI application.

    This function handles startup and shutdown logic for the application.
    Expensive objects (like Ollama clients and discovery services) are created
    once at startup and stored in app.state for reuse across all requests.

    Phase 0: No startup logic needed yet.
    Phase 1+: Will initialize Ollama clients and discovery services here.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded while the app is running.
    """
    # Startup logic (Phase 1+)
    # app.state.ollama_client = OllamaClient(...)
    # app.state.tool_discovery = ToolDiscoveryService(...)

    yield

    # Shutdown logic (if needed in future phases)
    pass


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

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)

    return app
