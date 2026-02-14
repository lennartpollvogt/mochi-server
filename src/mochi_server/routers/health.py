"""Health check endpoint router."""

from fastapi import APIRouter

from mochi_server.models.health import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns the current health status and version of the mochi-server.
    In Phase 0, this is a static response. Phase 1 will add Ollama connectivity checks.

    Returns:
        HealthResponse: Health status and version information.
    """
    return HealthResponse(
        status="ok",
        version="0.1.0",
    )
