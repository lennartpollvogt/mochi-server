"""mochi-server: Headless FastAPI server for LLM conversations via Ollama.

This package provides a REST API and SSE streaming interface for managing
chat sessions, executing tools, orchestrating agents, and more.
"""

from mochi_server.app import create_app

__version__ = "0.1.0"

__all__ = ["create_app", "__version__"]
