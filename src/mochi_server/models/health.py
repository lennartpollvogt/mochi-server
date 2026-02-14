"""Health check response model."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for the health check endpoint.

    Attributes:
        status: Health status indicator ("ok" or "error").
        version: The version of mochi-server.
        ollama_connected: Optional boolean indicating Ollama connectivity (added in Phase 1).
        ollama_host: Optional string with the Ollama host URL (added in Phase 1).
    """

    status: str = Field(..., description="Health status of the service")
    version: str = Field(..., description="Version of mochi-server")
    ollama_connected: bool | None = Field(
        default=None,
        description="Whether Ollama is connected (Phase 1+)",
    )
    ollama_host: str | None = Field(
        default=None,
        description="Ollama host URL (Phase 1+)",
    )
