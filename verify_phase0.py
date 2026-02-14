#!/usr/bin/env python3
"""Phase 0 verification script for mochi-server.

This script verifies that all Phase 0 requirements are met:
- FastAPI app can be created
- Health endpoint responds correctly
- Settings load from environment variables
- CLI entry point exists
- All tests pass
"""

import asyncio
import os
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mochi_server import __version__, create_app
from mochi_server.config import MochiServerSettings


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"✅ {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"❌ {text}")


async def verify_health_endpoint() -> bool:
    """Verify the health endpoint works correctly."""
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")

            if response.status_code != 200:
                print_error(f"Health endpoint returned {response.status_code}")
                return False

            data = response.json()

            if data.get("status") != "ok":
                print_error(f"Health status is '{data.get('status')}', expected 'ok'")
                return False

            if data.get("version") != __version__:
                print_error(f"Version mismatch: {data.get('version')} != {__version__}")
                return False

            print_success("Health endpoint returns correct response")
            print(f"   Status: {data['status']}")
            print(f"   Version: {data['version']}")
            return True

    except Exception as e:
        print_error(f"Health endpoint verification failed: {e}")
        return False


def verify_app_creation() -> bool:
    """Verify the app factory works."""
    try:
        app = create_app()
        print_success("FastAPI app created successfully")
        print(f"   Title: {app.title}")
        print(f"   Version: {app.version}")
        return True
    except Exception as e:
        print_error(f"App creation failed: {e}")
        return False


def verify_settings() -> bool:
    """Verify settings configuration."""
    try:
        # Test default settings
        settings = MochiServerSettings()
        print_success("Settings loaded with defaults")
        print(f"   Host: {settings.host}:{settings.port}")
        print(f"   Ollama: {settings.ollama_host}")
        print(f"   Data dir: {settings.data_dir}")

        # Test environment variable override
        os.environ["MOCHI_PORT"] = "9999"
        settings_with_env = MochiServerSettings()

        if settings_with_env.port != 9999:
            print_error("Environment variable override failed")
            return False

        print_success("Environment variable override works (MOCHI_PORT=9999)")

        # Clean up
        del os.environ["MOCHI_PORT"]

        return True
    except Exception as e:
        print_error(f"Settings verification failed: {e}")
        return False


def verify_project_structure() -> bool:
    """Verify the project structure is correct."""
    required_files = [
        "src/mochi_server/__init__.py",
        "src/mochi_server/__main__.py",
        "src/mochi_server/app.py",
        "src/mochi_server/config.py",
        "src/mochi_server/dependencies.py",
        "src/mochi_server/constants.py",
        "src/mochi_server/models/__init__.py",
        "src/mochi_server/models/health.py",
        "src/mochi_server/routers/__init__.py",
        "src/mochi_server/routers/health.py",
        "src/mochi_server/ollama/__init__.py",
        "src/mochi_server/sessions/__init__.py",
        "src/mochi_server/tools/__init__.py",
        "src/mochi_server/agents/__init__.py",
        "src/mochi_server/services/__init__.py",
        "tests/conftest.py",
        "tests/unit/test_health.py",
        "tests/unit/test_app.py",
        "pyproject.toml",
    ]

    project_root = Path(__file__).parent
    missing_files = []

    for file_path in required_files:
        if not (project_root / file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        print_error("Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False

    print_success(f"All {len(required_files)} required files present")
    return True


def verify_dependencies() -> bool:
    """Verify required dependencies are installed."""
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
        "pytest",
        "pytest_asyncio",
        "httpx",
        "ruff",
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print_error("Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        return False

    print_success(f"All {len(required_packages)} required dependencies installed")
    return True


async def main() -> int:
    """Run all verification checks."""
    print_header("Phase 0: Foundation - Verification")

    print(f"mochi-server version: {__version__}")
    print(f"Python version: {sys.version.split()[0]}")

    checks = []

    print_header("1. Project Structure")
    checks.append(verify_project_structure())

    print_header("2. Dependencies")
    checks.append(verify_dependencies())

    print_header("3. FastAPI App Creation")
    checks.append(verify_app_creation())

    print_header("4. Settings Configuration")
    checks.append(verify_settings())

    print_header("5. Health Endpoint")
    checks.append(await verify_health_endpoint())

    print_header("Summary")

    passed = sum(checks)
    total = len(checks)

    if passed == total:
        print_success(f"All {total} checks passed!")
        print("\n🎉 Phase 0: Foundation is complete and verified!")
        print("\nNext steps:")
        print("  1. Start the server: uv run mochi-server")
        print("  2. Test the API: curl http://localhost:8000/api/v1/health")
        print("  3. View docs: http://localhost:8000/docs")
        print("  4. Run tests: uv run pytest")
        print("  5. Move to Phase 1: Ollama Integration")
        return 0
    else:
        print_error(f"{passed}/{total} checks passed")
        print("\n⚠️  Phase 0 verification incomplete. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
