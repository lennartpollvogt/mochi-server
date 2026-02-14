"""Ollama client wrapper and integration layer.

This package provides async client wrappers for communicating with the Ollama API.
All Ollama interactions are async and use streaming by default.
"""

from mochi_server.ollama.client import OllamaClient
from mochi_server.ollama.types import ModelInfo

__all__ = ["OllamaClient", "ModelInfo"]
