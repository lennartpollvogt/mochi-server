"""Health check endpoint router."""

import logging

from fastapi import APIRouter, Request

from mochi_server.models.health import HealthResponse
from mochi_server.ollama import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint.

    Returns the current health status and version of the mochi-server.
    Also checks connectivity to the Ollama server if the client is initialized.

    Args:
        request: The FastAPI request object.

    Returns:
        HealthResponse: Health status and version information.
    """
    ollama_connected = None
    ollama_host = None

    # Check if Ollama client is available and test connectivity
    if hasattr(request.app.state, "ollama_client"):
        ollama_client: OllamaClient = request.app.state.ollama_client
        ollama_host = ollama_client.host

        try:
            ollama_connected = await ollama_client.check_connection()
            logger.debug(f"Ollama connectivity check: {ollama_connected}")
        except Exception as e:
            logger.warning(f"Ollama connectivity check failed: {e}")
            ollama_connected = False

    return HealthResponse(
        status="ok",
        version="0.1.0",
        ollama_connected=ollama_connected,
        ollama_host=ollama_host,
    )
