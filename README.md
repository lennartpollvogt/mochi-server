# mochi-server

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**mochi-server** is a headless FastAPI server that provides a REST API and SSE streaming interface for LLM conversations via Ollama. It manages persistent chat sessions, tool execution, agent orchestration, and more.

## 🚀 Status: Phase 0 Complete

**Phase 0: Foundation** ✅

The server now has:
- FastAPI application with health check endpoint
- Configuration via environment variables (pydantic-settings)
- Complete project structure scaffolded
- CLI entry point (`mochi-server` command)
- Full test suite with pytest
- Type-safe code with Pydantic models

## 📦 Installation

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/mochi-server.git
cd mochi-server

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## 🏃 Quick Start

### Start the Server

```bash
# Using the CLI entry point
mochi-server

# Or with Python module
python -m mochi_server

# Custom host and port
mochi-server --host 0.0.0.0 --port 9000

# Enable auto-reload for development
mochi-server --reload
```

### Test the Health Endpoint

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "ollama_connected": null,
  "ollama_host": null
}
```

## ⚙️ Configuration

All settings can be configured via environment variables with the `MOCHI_` prefix:

```bash
# Server configuration
export MOCHI_HOST=0.0.0.0
export MOCHI_PORT=9000

# Ollama configuration (Phase 1+)
export MOCHI_OLLAMA_HOST=http://localhost:11434

# Data directories
export MOCHI_DATA_DIR=/path/to/data

# Logging
export MOCHI_LOG_LEVEL=DEBUG
```

Or via command-line arguments:

```bash
mochi-server --host 0.0.0.0 --port 9000 --data-dir /path/to/data --log-level DEBUG
```

## 🧪 Development

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mochi_server tests/

# Run specific test file
uv run pytest tests/unit/test_health.py -v
```

### Code Quality

```bash
# Check code style
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Project Structure

```
mochi-server/
├── src/
│   └── mochi_server/
│       ├── __init__.py          # Package init, create_app()
│       ├── __main__.py          # CLI entry point
│       ├── app.py               # FastAPI app factory
│       ├── config.py            # Settings (pydantic-settings)
│       ├── dependencies.py      # FastAPI dependency injection
│       ├── constants.py         # Shared constants
│       ├── models/              # Pydantic request/response schemas
│       ├── routers/             # FastAPI route handlers
│       ├── ollama/              # Ollama client wrappers (Phase 1+)
│       ├── sessions/            # Session management (Phase 2+)
│       ├── tools/               # Tool system (Phase 7+)
│       ├── agents/              # Agent system (Phase 8+)
│       └── services/            # Business logic services
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   └── unit/                    # Unit tests
├── app_specs/                   # Technical specifications
└── pyproject.toml              # Project configuration
```

## 📚 API Documentation

Once the server is running, visit:
- **Interactive API docs (Swagger):** http://localhost:8000/docs
- **Alternative API docs (ReDoc):** http://localhost:8000/redoc

### Current Endpoints (Phase 0)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check with version info |

## 🗺️ Roadmap

- [x] **Phase 0: Foundation** - Basic server structure
- [ ] **Phase 1: Ollama Integration** - Connect to Ollama, list models
- [ ] **Phase 2: Sessions & Persistence** - Session CRUD with JSON files
- [ ] **Phase 3: Non-Streaming Chat** - Basic chat functionality
- [ ] **Phase 4: Streaming Chat** - SSE streaming with real-time responses
- [ ] **Phase 5: System Prompts** - Prompt management
- [ ] **Phase 6: Context Window Management** - Dynamic context sizing
- [ ] **Phase 7: Tool System** - Tool discovery and execution
- [ ] **Phase 8: Agent System** - Two-phase agent orchestration
- [ ] **Phase 9: Summarization** - Background conversation summaries

## 📖 Documentation

- [Full Specification](app_specs/mochi_server_specs.md) - Complete technical spec
- [Evolution Plan](app_specs/mochi_server_evolution_steps.md) - Phase-by-phase implementation guide
- [Development Rules](app_specs/mochi_server_rules.md) - Coding standards and constraints

## 🛠️ Technology Stack

- **Framework:** FastAPI 0.115+
- **Server:** uvicorn
- **Validation:** Pydantic v2
- **Configuration:** pydantic-settings
- **Testing:** pytest + pytest-asyncio + httpx
- **Code Quality:** ruff
- **Python:** 3.11+

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! This project follows a strict phase-based development approach. Please ensure:

1. All new code follows the specifications in `app_specs/`
2. Tests are included for all new functionality
3. Code passes `ruff check` and `ruff format`
4. Type hints are used throughout

## 🙋 Support

For questions or issues, please open an issue on GitHub.

---

Built with ❤️ using FastAPI and Ollama