"""CLI entry point for mochi-server.

This module provides the command-line interface for starting the mochi-server.
It can be invoked as `mochi-server` (via the script entry point) or
`python -m mochi_server`.
"""

import argparse
import sys

import uvicorn

from mochi_server import __version__, create_app
from mochi_server.config import MochiServerSettings


def main() -> None:
    """Main entry point for the mochi-server CLI.

    Parses command-line arguments and starts the uvicorn server with the
    FastAPI application.
    """
    parser = argparse.ArgumentParser(
        prog="mochi-server",
        description="Headless FastAPI server for LLM conversations via Ollama",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"mochi-server {__version__}",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind the server to (default: 127.0.0.1, can be set via MOCHI_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind the server to (default: 8000, can be set via MOCHI_PORT)",
    )

    parser.add_argument(
        "--ollama-host",
        type=str,
        default=None,
        help="Ollama server URL (default: http://localhost:11434, can be set via MOCHI_OLLAMA_HOST)",
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Base directory for all data (default: ., can be set via MOCHI_DATA_DIR)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO, can be set via MOCHI_LOG_LEVEL)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development (uvicorn --reload)",
    )

    args = parser.parse_args()

    # Build settings, CLI args override environment variables
    settings_kwargs = {}
    if args.host is not None:
        settings_kwargs["host"] = args.host
    if args.port is not None:
        settings_kwargs["port"] = args.port
    if args.ollama_host is not None:
        settings_kwargs["ollama_host"] = args.ollama_host
    if args.data_dir is not None:
        settings_kwargs["data_dir"] = args.data_dir
    if args.log_level is not None:
        settings_kwargs["log_level"] = args.log_level

    settings = MochiServerSettings(**settings_kwargs)

    # Create the FastAPI app
    app = create_app(settings=settings)

    # Start uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=args.reload,
    )


if __name__ == "__main__":
    sys.exit(main())
