# Mochi Server Specification

> **Version:** 0.1.0-draft
> **Status:** Initial Specification
> **Author:** Lennart Pollvogt

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Package & Distribution](#3-package--distribution)
4. [Project Structure](#4-project-structure)
5. [Dependency Management](#5-dependency-management)
6. [Configuration](#6-configuration)
7. [Architecture Overview](#7-architecture-overview)
8. [Data Models](#8-data-models)
9. [API Specification](#9-api-specification)
10. [Core Flows](#10-core-flows)
11. [Ollama Integration Layer](#11-ollama-integration-layer)
12. [Session Management](#12-session-management)
13. [Tool System](#13-tool-system)
14. [Agent System](#14-agent-system)
15. [Context Window Management](#15-context-window-management)
16. [Summarization Service](#16-summarization-service)
17. [System Prompt Management](#17-system-prompt-management)
18. [Streaming & Real-Time Communication](#18-streaming--real-time-communication)
19. [Error Handling](#19-error-handling)
20. [Testing Strategy](#20-testing-strategy)
---

## 1. Overview

**mochi-server** is a Python FastAPI application that acts as a headless server connecting to an Ollama instance and exposes RESTful (and streaming) APIs for:

- Conversing with LLMs (streaming and non-streaming)
- Managing persistent chat sessions
- Discovering, configuring, and executing tools
- Discovering, configuring, and executing agents (two-phase planning + execution)
- Managing system prompts
- Dynamic context window management
- Background conversation summarization

The Ollama server runs independently and is **not** managed by mochi-server. mochi-server simply connects to it.

Any frontend — CLI, web UI, desktop app, or another service — can consume mochi-server's API to build LLM-powered chat experiences.

---

## 2. Goals & Non-Goals

### 2.1 Goals

- **Headless backend:** All business logic runs behind HTTP APIs. Zero UI code.
- **PyPI package:** Installable via `pip install mochi-server` (or `uv add mochi-server`).
- **Importable library:** Core modules can be imported directly in Python code without running the server (e.g., `from mochi_server.sessions import SessionManager`).
- **Complete feature set:** Sessions, tools, agents, summarization, context window management, and system prompts.
- **Streaming support:** Server-Sent Events (SSE) for real-time chat streaming.
- **Stateless API design:** The server itself is stateless; all state lives in session JSON files and configuration. This makes horizontal scaling trivial in the future.
- **Extensible tool & agent system:** Users drop Python files into designated directories, and the server discovers them automatically.

### 2.2 Non-Goals

- **No UI:** mochi-server does not render markdown, display menus, or handle terminal I/O.
- **No Ollama management:** mochi-server does not start, stop, or manage the Ollama process.
- **No authentication (v1):** The first version runs locally without auth. Auth can be added later as middleware.
- **No database:** Session persistence uses JSON files on disk. A database backend can be added later behind an abstraction.

---

## 3. Package & Distribution

### 3.1 Package Name

- **PyPI name:** `mochi-server`
- **Import name:** `mochi_server`

### 3.2 Installation

```bash
# Install from PyPI
pip install mochi-server

# Or with uv
uv add mochi-server
```

### 3.3 Entry Points

The package provides a CLI entry point to start the server:

```bash
# Start the server (default: http://localhost:8000)
mochi-server

# Custom host and port
mochi-server --host 0.0.0.0 --port 9000

# Custom Ollama host
mochi-server --ollama-host http://192.168.1.100:11434

# Custom data directory (sessions, tools, agents, system_prompts)
mochi-server --data-dir /path/to/data
```

### 3.4 Programmatic Usage

```python
from mochi_server import create_app

app = create_app(
    ollama_host="http://localhost:11434",
    data_dir="./my_data",
)

# Run with uvicorn
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Or import individual modules:

```python
from mochi_server.sessions import SessionManager
from mochi_server.ollama import OllamaClient
from mochi_server.tools import ToolDiscoveryService

client = OllamaClient(host="http://localhost:11434")
models = client.list_models()
```

---

## 4. Project Structure

```
mochi-server/
├── src/
│   └── mochi_server/
│       ├── __init__.py              # Package init, create_app factory
│       ├── __main__.py              # CLI entry point (mochi-server command)
│       ├── py.typed                 # PEP 561 marker
│       ├── app.py                   # FastAPI app factory & lifespan
│       ├── config.py                # Settings via pydantic-settings
│       ├── dependencies.py          # FastAPI dependency injection
│       │
│       ├── models/                  # Pydantic request/response models
│       │   ├── __init__.py
│       │   ├── chat.py              # Chat request/response schemas
│       │   ├── sessions.py          # Session schemas
│       │   ├── tools.py             # Tool schemas
│       │   ├── agents.py            # Agent schemas
│       │   ├── models.py            # Ollama model schemas
│       │   └── system_prompts.py    # System prompt schemas
│       │
│       ├── routers/                 # FastAPI route handlers
│       │   ├── __init__.py
│       │   ├── chat.py              # /api/v1/chat/*
│       │   ├── sessions.py          # /api/v1/sessions/*
│       │   ├── tools.py             # /api/v1/tools/*
│       │   ├── agents.py            # /api/v1/agents/*
│       │   ├── models.py            # /api/v1/models/*
│       │   ├── system_prompts.py    # /api/v1/system-prompts/*
│       │   └── health.py            # /api/v1/health
│       │
│       ├── ollama/                  # Ollama client layer
│       │   ├── __init__.py
│       │   ├── client.py            # Sync OllamaClient
│       │   ├── async_client.py      # AsyncOllamaClient + AsyncInstructorOllamaClient
│       │   └── types.py             # ModelInfo, ChatMessage dataclasses
│       │
│       ├── sessions/                # Session management
│       │   ├── __init__.py
│       │   ├── session.py           # ChatSession, message types, metadata
│       │   ├── manager.py           # SessionManager (CRUD operations)
│       │   └── types.py             # SessionCreationOptions, results
│       │
│       ├── tools/                   # Tool system
│       │   ├── __init__.py
│       │   ├── config.py            # ToolSettings, ToolExecutionPolicy
│       │   ├── discovery.py         # ToolDiscoveryService
│       │   ├── schema.py            # ToolSchemaService
│       │   └── execution.py         # ToolExecutionService, ToolExecutionResult
│       │
│       ├── agents/                  # Agent system
│       │   ├── __init__.py
│       │   ├── config.py            # AgentSettings
│       │   ├── discovery.py         # AgentDiscoveryService, AgentDefinition
│       │   ├── execution.py         # AgentExecutionService (two-phase loop)
│       │   ├── tool_factory.py      # Dynamic agent tool builder
│       │   └── prompt_loader.py     # Ephemeral planning/execution prompts
│       │
│       ├── services/                # Cross-cutting services
│       │   ├── __init__.py
│       │   ├── context_window.py    # DynamicContextWindowService
│       │   ├── summarization.py     # SummarizationService
│       │   ├── summary_model.py     # SummaryModelManager
│       │   └── system_prompts.py    # SystemPromptService
│       │
│       └── constants.py             # Shared constants (unsupported models, etc.)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures (TestClient, mock Ollama)
│   ├── unit/                        # Unit tests
│   │   ├── test_session.py
│   │   ├── test_tool_discovery.py
│   │   ├── test_tool_execution.py
│   │   ├── test_agent_discovery.py
│   │   ├── test_agent_execution.py
│   │   ├── test_context_window.py
│   │   ├── test_system_prompts.py
│   │   └── test_summarization.py
│   └── integration/                 # Integration tests (require Ollama or mocks)
│       ├── test_chat_api.py
│       ├── test_session_api.py
│       ├── test_tool_api.py
│       └── test_agent_api.py
│
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
└── .gitignore
```

---

## 5. Dependency Management

### 5.1 Tooling

The project uses **`uv`** as the dependency manager and build tool.

```bash
# Create project
uv init mochi-server

# Add dependencies
uv add fastapi uvicorn[standard] ollama ollama-instructor pydantic pydantic-settings sse-starlette

# Add dev dependencies
uv add --group dev pytest pytest-asyncio httpx ruff mypy

# Run the server
uv run mochi-server

# Run tests
uv run pytest
```

### 5.2 pyproject.toml

```toml
[project]
name = "mochi-server"
version = "0.1.0"
description = "A FastAPI server for LLM conversations via Ollama with session persistence, tool execution, and agent orchestration."
readme = "README.md"
authors = [
    { name = "Lennart Pollvogt", email = "lennartpollvogt@protonmail.com" },
]
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "ollama>=0.5.3",
    "ollama-instructor>=1.1.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "sse-starlette>=2.0.0",
]

[project.scripts]
mochi-server = "mochi_server.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.4.0",
    "pytest-asyncio>=1.0.0",
    "httpx>=0.28.0",
    "ruff>=0.12.0",
    "mypy>=1.15.0",
]
```

### 5.3 Python Version

Minimum **Python 3.10**.

---

## 6. Configuration

Configuration is handled via **pydantic-settings** with environment variable support.

### 6.1 Settings Model

```python
from pydantic_settings import BaseSettings

class MochiServerSettings(BaseSettings):
    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Ollama
    ollama_host: str = "http://localhost:11434"

    # Data directories (relative to data_dir)
    data_dir: str = "."          # Base directory for all data
    sessions_dir: str = "chat_sessions"
    tools_dir: str = "tools"
    agents_dir: str = "agents"
    agent_chats_dir: str = "agents/agent_chats"
    system_prompts_dir: str = "system_prompts"

    # Planning/execution prompt paths
    planning_prompt_path: str = "docs/agents/agent_prompt_planning.md"
    execution_prompt_path: str = "docs/agents/agent_prompt_execution.md"

    # Summarization
    summarization_enabled: bool = True
    summarization_interval_seconds: int = 3

    # Context window
    dynamic_context_window_enabled: bool = True

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "MOCHI_"}
```

### 6.2 Environment Variables

All settings can be overridden via environment variables prefixed with `MOCHI_`:

```bash
export MOCHI_OLLAMA_HOST=http://192.168.1.100:11434
export MOCHI_DATA_DIR=/var/lib/mochi
export MOCHI_PORT=9000
export MOCHI_LOG_LEVEL=DEBUG
```

---

## 7. Architecture Overview

```
┌──────────────┐     HTTP/SSE      ┌─────────────────┐      Ollama API     ┌──────────────┐
│              │  ◄──────────────►  │                 │  ◄────────────────►  │              │
│   Frontend   │                   │  mochi-server   │                     │    Ollama    │
│  (any client)│                   │   (FastAPI)     │                     │    Server    │
│              │                   │                 │                     │              │
└──────────────┘                   └────────┬────────┘                     └──────────────┘
                                            │
                                            │ File I/O
                                            ▼
                                   ┌─────────────────┐
                                   │   Data Layer     │
                                   │                 │
                                   │ • chat_sessions/ │
                                   │ • tools/        │
                                   │ • agents/       │
                                   │ • system_prompts/│
                                   └─────────────────┘
```

### 7.1 Layer Responsibilities

| Layer | Responsibility |
|---|---|
| **Routers** | HTTP request/response handling, validation, SSE streaming |
| **Services** | Business logic, orchestration, state management |
| **Ollama Client** | Communication with Ollama API (sync + async) |
| **Sessions** | Chat session CRUD, message management, persistence |
| **Tools** | Discovery, schema conversion, execution |
| **Agents** | Discovery, two-phase execution, agent session management |
| **Models (Pydantic)** | Request/response validation, serialization |
| **Config** | Application configuration via env vars / settings |

### 7.2 Dependency Injection

FastAPI's dependency injection system is used to provide services to route handlers:

```python
from fastapi import Depends

def get_ollama_client(settings = Depends(get_settings)) -> OllamaClient:
    return OllamaClient(host=settings.ollama_host)

def get_session_manager(settings = Depends(get_settings)) -> SessionManager:
    return SessionManager(sessions_dir=settings.resolved_sessions_dir)

@router.get("/sessions")
async def list_sessions(manager: SessionManager = Depends(get_session_manager)):
    return manager.list_sessions()
```

---

## 8. Data Models

### 8.1 Message Types

mochi-server uses the following message types:

| Type | Role | Fields |
|---|---|---|
| **UserMessage** | `"user"` | `content`, `message_id`, `timestamp` |
| **SystemMessage** | `"system"` | `content`, `source_file`, `message_id`, `timestamp` |
| **AssistantMessage** | `"assistant"` | `content`, `model`, `message_id`, `timestamp`, `eval_count`, `prompt_eval_count`, `tool_calls` |
| **ToolMessage** | `"tool"` | `content`, `tool_name`, `message_id`, `timestamp` |

### 8.2 Session Metadata

```python
class SessionMetadata:
    session_id: str
    model: str
    created_at: str       # ISO 8601
    updated_at: str       # ISO 8601
    message_count: int
    summary: dict | None           # {summary: str, topics: list[str]}
    summary_model: str | None
    format_version: str            # "1.3"
    tool_settings: ToolSettings | None
    agent_settings: AgentSettings | None
    context_window_config: dict | None
```

### 8.3 Tool Settings

```python
class ToolExecutionPolicy(str, Enum):
    ALWAYS_CONFIRM = "always_confirm"
    NEVER_CONFIRM = "never_confirm"
    CONFIRM_DESTRUCTIVE = "confirm_destructive"

class ToolSettings:
    tools: list[str]                          # Individual tool names
    tool_group: str | None                    # Selected tool group
    execution_policy: ToolExecutionPolicy
```

### 8.4 Agent Settings

```python
class AgentSettings:
    enabled_agents: list[str]
    selection_metadata: dict | None
```

### 8.5 Agent Definition

```python
class AgentDefinition:
    name: str
    description: str
    system_prompt: str
    model: str | None
    tools: dict[str, Callable]
    valid: bool
    error_message: str | None
```

---

## 9. API Specification

All endpoints are prefixed with `/api/v1`.

### 9.1 Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Server health check + Ollama connectivity |

**Response:**
```json
{
  "status": "ok",
  "ollama_connected": true,
  "ollama_host": "http://localhost:11434",
  "version": "0.1.0"
}
```

---

### 9.2 Models

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/models` | List all available Ollama models |
| `GET` | `/api/v1/models/{model_name}` | Get details for a specific model |

**GET /api/v1/models — Response:**
```json
{
  "models": [
    {
      "name": "qwen3:14b",
      "size_mb": 9048.2,
      "format": "gguf",
      "family": "qwen3",
      "parameter_size": "14.8B",
      "quantization_level": "Q4_K_M",
      "capabilities": ["completion", "tools"],
      "context_length": 40960
    }
  ]
}
```

---

### 9.3 Sessions

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/sessions` | List all sessions (sorted by updated_at desc) |
| `POST` | `/api/v1/sessions` | Create a new session |
| `GET` | `/api/v1/sessions/{session_id}` | Get session details + full message history |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete a session |
| `PATCH` | `/api/v1/sessions/{session_id}` | Update session metadata (model, tool_settings, agent_settings) |
| `GET` | `/api/v1/sessions/{session_id}/messages` | Get messages for a session |
| `PUT` | `/api/v1/sessions/{session_id}/messages/{message_index}` | Edit a message and truncate subsequent messages |
| `PUT` | `/api/v1/sessions/{session_id}/system-prompt` | Set or update system prompt for a session |
| `DELETE` | `/api/v1/sessions/{session_id}/system-prompt` | Remove system prompt from a session |

**POST /api/v1/sessions — Request:**
```json
{
  "model": "qwen3:14b",
  "system_prompt": "You are a helpful assistant.",
  "system_prompt_source_file": "helpful.md",
  "tool_settings": {
    "tools": ["add_numbers", "get_current_time"],
    "tool_group": null,
    "execution_policy": "always_confirm"
  },
  "agent_settings": {
    "enabled_agents": ["coder"]
  }
}
```

**POST /api/v1/sessions — Response:**
```json
{
  "session_id": "a1b2c3d4e5",
  "model": "qwen3:14b",
  "created_at": "2025-01-15T10:30:00.000000",
  "updated_at": "2025-01-15T10:30:00.000000",
  "message_count": 0,
  "tool_settings": { "..." },
  "agent_settings": { "..." }
}
```

**GET /api/v1/sessions — Response:**
```json
{
  "sessions": [
    {
      "session_id": "a1b2c3d4e5",
      "model": "qwen3:14b",
      "created_at": "2025-01-15T10:30:00.000000",
      "updated_at": "2025-01-15T10:35:00.000000",
      "message_count": 6,
      "summary": {
        "summary": "User asked about Python async patterns...",
        "topics": ["python", "asyncio", "concurrency"]
      },
      "preview": "How do I use asyncio in Python?"
    }
  ]
}
```

**PUT /api/v1/sessions/{session_id}/messages/{message_index} — Request:**
```json
{
  "content": "Updated message content"
}
```

---

### 9.4 Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/{session_id}` | Send a message and get a non-streaming response |
| `POST` | `/api/v1/chat/{session_id}/stream` | Send a message and get a streaming SSE response |

**POST /api/v1/chat/{session_id} — Request:**
```json
{
  "message": "What is the capital of France?",
  "think": false
}
```

**POST /api/v1/chat/{session_id} — Response (non-streaming):**
```json
{
  "session_id": "a1b2c3d4e5",
  "message": {
    "role": "assistant",
    "content": "The capital of France is Paris.",
    "model": "qwen3:14b",
    "message_id": "f1e2d3c4b5",
    "timestamp": "2025-01-15T10:35:00.000000",
    "eval_count": 45,
    "prompt_eval_count": 120
  },
  "tool_calls_executed": [],
  "context_window": {
    "current_window": 8192,
    "usage_tokens": 165,
    "reason": "initial_setup"
  }
}
```

**POST /api/v1/chat/{session_id}/stream — SSE Response:**

The streaming endpoint returns Server-Sent Events. Each event has a `type` field:

```
event: content_delta
data: {"content": "The capital", "role": "assistant"}

event: content_delta
data: {"content": " of France", "role": "assistant"}

event: content_delta
data: {"content": " is Paris.", "role": "assistant"}

event: tool_call
data: {"tool_name": "get_current_time", "arguments": {}, "call_index": 0}

event: tool_result
data: {"tool_name": "get_current_time", "success": true, "result": "Current time: 2025-01-15 10:35:00", "call_index": 0}

event: tool_continuation_start
data: {"message": "Processing tool results..."}

event: content_delta
data: {"content": "The current time is...", "role": "assistant"}

event: message_complete
data: {"message_id": "f1e2d3c4b5", "model": "qwen3:14b", "eval_count": 45, "prompt_eval_count": 120, "context_window": {"current_window": 8192}}

event: done
data: {"session_id": "a1b2c3d4e5"}
```

**SSE Event Types:**

| Event Type | Description |
|---|---|
| `content_delta` | Incremental content chunk from the LLM |
| `thinking_delta` | Incremental thinking block content (when `think=true`) |
| `tool_call` | LLM requested a tool call |
| `tool_call_confirmation_required` | Tool requires user confirmation (when policy is `always_confirm`) |
| `tool_result` | Result of tool execution |
| `tool_continuation_start` | Conversation continuing after tool execution |
| `agent_start` | Agent execution started |
| `agent_planning` | Agent planning phase content |
| `agent_execution` | Agent execution phase content |
| `agent_tool_call` | Agent made a tool call |
| `agent_tool_result` | Result of agent tool execution |
| `agent_complete` | Agent execution finished |
| `message_complete` | Full message metadata after streaming finishes |
| `error` | An error occurred |
| `done` | Stream is complete |

---

### 9.5 Tool Confirmation Flow (Streaming)

When the execution policy is `always_confirm`, tool calls require explicit approval:

```
event: tool_call_confirmation_required
data: {"tool_name": "delete_file", "arguments": {"path": "/tmp/test.txt"}, "call_index": 0, "confirmation_id": "conf_abc123"}
```

The client must then call:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/{session_id}/confirm-tool` | Approve or deny a pending tool call |

**Request:**
```json
{
  "confirmation_id": "conf_abc123",
  "approved": true
}
```

If the client does not respond within a configurable timeout, the tool call is denied.

For the `never_confirm` policy, tools execute immediately and `tool_call` + `tool_result` events are emitted without waiting.

---

### 9.6 Tools

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/tools` | List all discovered tools and tool groups |
| `GET` | `/api/v1/tools/{tool_name}` | Get details for a specific tool (schema, description) |
| `POST` | `/api/v1/tools/reload` | Force reload tools from disk |

**GET /api/v1/tools — Response:**
```json
{
  "tools": {
    "add_numbers": {
      "name": "add_numbers",
      "description": "Add two numbers together.",
      "parameters": {
        "a": {"type": "float", "description": "The first number to add."},
        "b": {"type": "float", "description": "The second number to add."}
      }
    }
  },
  "groups": {
    "math": ["add_numbers", "subtract_numbers", "multiply_numbers", "divide_numbers"],
    "utilities": ["get_current_time", "flip_coin", "roll_dice"]
  }
}
```

---

### 9.7 Agents

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/agents` | List all discovered agents |
| `GET` | `/api/v1/agents/{agent_name}` | Get details for a specific agent |
| `POST` | `/api/v1/agents/reload` | Force reload agents from disk |
| `GET` | `/api/v1/agents/chats` | List all agent chat sessions |
| `GET` | `/api/v1/agents/chats/{session_id}` | Get an agent chat session |

**GET /api/v1/agents — Response:**
```json
{
  "agents": {
    "coder": {
      "name": "coder",
      "description": "A coding agent with file system operations...",
      "model": null,
      "valid": true,
      "tool_count": 6,
      "tools": ["read_file", "write_file", "insert_replace_text", "list_dir", "delete_rename_file", "run_cli_command"]
    },
    "agent_builder": {
      "name": "agent_builder",
      "description": "An agent specialized in creating new agents...",
      "model": null,
      "valid": true,
      "tool_count": 6,
      "tools": ["read_file", "write_file", "insert_replace_text", "list_dir", "delete_rename_file", "run_cli_command"]
    }
  }
}
```

---

### 9.8 System Prompts

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/system-prompts` | List all available system prompt files |
| `GET` | `/api/v1/system-prompts/{filename}` | Get content of a specific system prompt |
| `POST` | `/api/v1/system-prompts` | Create a new system prompt file |
| `PUT` | `/api/v1/system-prompts/{filename}` | Update an existing system prompt file |
| `DELETE` | `/api/v1/system-prompts/{filename}` | Delete a system prompt file |

**GET /api/v1/system-prompts — Response:**
```json
{
  "prompts": [
    {
      "filename": "using_agents.md",
      "preview": "You have access to specialized agents...",
      "word_count": 245
    }
  ]
}
```

---

### 9.9 Context Window & Status

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/sessions/{session_id}/status` | Get session status including context window info |

**Response:**
```json
{
  "session_id": "a1b2c3d4e5",
  "model": "qwen3:14b",
  "message_count": 12,
  "context_window": {
    "dynamic_enabled": true,
    "current_window": 8192,
    "model_max_context": 40960,
    "last_adjustment_reason": "usage_threshold",
    "manual_override": false
  },
  "tools_enabled": true,
  "active_tools": ["add_numbers", "get_current_time"],
  "execution_policy": "always_confirm",
  "agents_enabled": true,
  "enabled_agents": ["coder"],
  "system_prompt_file": "using_agents.md",
  "summary": {
    "summary": "Discussion about Python patterns...",
    "topics": ["python", "design patterns"]
  },
  "summary_model": "qwen3:14b"
}
```

---

### 9.10 Summarization

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/sessions/{session_id}/summarize` | Trigger immediate summary generation |
| `GET` | `/api/v1/sessions/{session_id}/summary` | Get current session summary |

**POST /api/v1/sessions/{session_id}/summarize — Request:**
```json
{
  "model": "qwen3:14b"
}
```

**Response:**
```json
{
  "summary": "User discussed Python async patterns and best practices for concurrent programming.",
  "topics": ["python", "asyncio", "concurrency"],
  "model_used": "qwen3:14b"
}
```

---

## 10. Core Flows

### 10.1 Flow: New Session → Chat Message → Response

```
Client                          mochi-server                       Ollama
  │                                  │                                │
  │  POST /sessions                  │                                │
  │  {model: "qwen3:14b"}           │                                │
  │ ────────────────────────────────►│                                │
  │                                  │                                │
  │  ◄──── 201 {session_id}         │                                │
  │                                  │                                │
  │  POST /chat/{id}/stream          │                                │
  │  {message: "Hello!"}            │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  1. Add user msg to session    │
  │                                  │  2. Calculate context window   │
  │                                  │  3. chat_stream()              │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: content_delta       │  ◄──── streaming chunks        │
  │  ◄──── SSE: content_delta       │                                │
  │  ◄──── SSE: content_delta       │                                │
  │  ◄──── SSE: message_complete    │  4. Save assistant msg         │
  │  ◄──── SSE: done                │                                │
  │                                  │  5. Trigger bg summarization   │
```

### 10.2 Flow: Chat Message with Tool Calls (never_confirm)

```
Client                          mochi-server                       Ollama
  │                                  │                                │
  │  POST /chat/{id}/stream          │                                │
  │  {message: "What time is it?"}  │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  1. Prepare tool schemas       │
  │                                  │  2. chat_stream(tools=...)     │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: tool_call           │  ◄──── tool_calls detected     │
  │        {get_current_time, {}}   │                                │
  │                                  │  3. Execute tool immediately   │
  │  ◄──── SSE: tool_result         │  4. Save tool call + result    │
  │        {success, "10:35:00"}    │                                │
  │                                  │                                │
  │  ◄──── SSE: tool_continuation   │  5. Continue with tool result  │
  │                                  │  chat_stream(messages+result)  │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: content_delta       │  ◄──── streaming response      │
  │  ◄──── SSE: message_complete    │  6. Save final assistant msg   │
  │  ◄──── SSE: done                │                                │
```

### 10.3 Flow: Chat Message with Tool Calls (always_confirm)

```
Client                          mochi-server                       Ollama
  │                                  │                                │
  │  POST /chat/{id}/stream          │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  chat_stream(tools=...)        │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: tool_call_          │  ◄──── tool_calls detected     │
  │        confirmation_required    │                                │
  │        {conf_id, tool, args}    │  (server pauses, waits)        │
  │                                  │                                │
  │  POST /chat/{id}/confirm-tool   │                                │
  │  {conf_id, approved: true}      │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  Execute tool                  │
  │  ◄──── SSE: tool_result         │  Save tool call + result       │
  │  ◄──── SSE: tool_continuation   │                                │
  │                                  │  Continue conversation         │
  │  ◄──── SSE: content_delta       │ ──────────────────────────────►│
  │  ◄──── SSE: message_complete    │                                │
  │  ◄──── SSE: done                │                                │
```

### 10.4 Flow: Agent Execution (Two-Phase)

```
Client                          mochi-server                       Ollama
  │                                  │                                │
  │  (During chat stream, LLM       │                                │
  │   calls agent tool)             │                                │
  │                                  │                                │
  │  ◄──── SSE: agent_start         │                                │
  │        {agent: "coder"}         │                                │
  │                                  │  ── PHASE 1: PLANNING ──      │
  │                                  │  1. Create/load agent session  │
  │                                  │  2. Refresh system prompt      │
  │                                  │  3. Add instruction as user msg│
  │                                  │  4. Append ephemeral planning  │
  │                                  │     prompt (not persisted)     │
  │                                  │  5. chat_stream (NO tools)     │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: agent_planning      │  ◄──── planning response       │
  │        {content: "Plan: ..."}   │  6. Save planning response     │
  │                                  │                                │
  │                                  │  ── PHASE 2: EXECUTION ──     │
  │                                  │  7. Append ephemeral execution │
  │                                  │     prompt (not persisted)     │
  │                                  │  8. chat_stream (WITH tools)   │
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: agent_tool_call     │  ◄──── tool_calls              │
  │                                  │  9. Execute agent tools        │
  │  ◄──── SSE: agent_tool_result   │  10. Save tool call + result   │
  │                                  │                                │
  │                                  │  11. Loop: send updated history│
  │                                  │ ──────────────────────────────►│
  │                                  │                                │
  │  ◄──── SSE: agent_execution     │  ◄──── text response (no tools)│
  │        {content: "Done..."}     │  12. Save final response       │
  │                                  │                                │
  │  ◄──── SSE: agent_complete      │  13. Format output with        │
  │        {session_id, output}     │      Session ID                │
  │                                  │                                │
  │  (Chat continues with agent     │  14. Continue main LLM         │
  │   output as tool result)        │      conversation              │
  │  ◄──── SSE: content_delta       │ ──────────────────────────────►│
  │  ◄──── SSE: message_complete    │                                │
  │  ◄──── SSE: done                │                                │
```

### 10.5 Flow: Session Switch

```
Client                          mochi-server
  │                                  │
  │  GET /sessions                   │
  │ ────────────────────────────────►│
  │  ◄──── [{session_id, ...}, ...] │
  │                                  │
  │  GET /sessions/{other_id}        │
  │ ────────────────────────────────►│
  │  ◄──── {session + messages}     │
  │                                  │
  │  (Client now sends chat msgs    │
  │   to the new session_id)        │
```

### 10.6 Flow: Edit Message and Re-generate

```
Client                          mochi-server                       Ollama
  │                                  │                                │
  │  PUT /sessions/{id}/             │                                │
  │      messages/{index}            │                                │
  │  {content: "Updated question"}  │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  1. Edit message at index      │
  │                                  │  2. Truncate all msgs after    │
  │  ◄──── 200 OK                   │  3. Save session               │
  │                                  │                                │
  │  POST /chat/{id}/stream          │                                │
  │  (empty - re-generates from     │                                │
  │   last user message)            │                                │
  │ ────────────────────────────────►│                                │
  │                                  │  chat_stream()                 │
  │                                  │ ──────────────────────────────►│
  │  ◄──── SSE: content_delta       │                                │
  │  ◄──── SSE: done                │                                │
```

### 10.7 Flow: Background Summarization

```
mochi-server (internal)                                   Ollama
  │                                                         │
  │  (After each assistant message is saved)                │
  │                                                         │
  │  1. Check if summary update needed                      │
  │     - At least 2 messages                               │
  │     - Last message is from assistant                    │
  │     - Last message has no tool_calls                    │
  │                                                         │
  │  2. Determine summary model                             │
  │     - Use chat model if it supports structured output   │
  │     - Use session's stored summary_model otherwise      │
  │     - Skip if no suitable model                         │
  │                                                         │
  │  3. Generate structured summary                         │
  │     (via AsyncInstructorOllamaClient)                   │
  │ ───────────────────────────────────────────────────────►│
  │                                                         │
  │  ◄──── ConversationSummary {summary, topics}            │
  │                                                         │
  │  4. Save summary to session metadata                    │
  │  5. Persist session JSON                                │
```

### 10.8 Flow: System Prompt Operations

```
Client                          mochi-server
  │                                  │
  │  GET /system-prompts             │
  │ ────────────────────────────────►│
  │  ◄──── [prompt files list]      │
  │                                  │
  │  GET /system-prompts/helpful.md  │
  │ ────────────────────────────────►│
  │  ◄──── {filename, content}      │
  │                                  │
  │  PUT /sessions/{id}/system-prompt│
  │  {content: "...",               │
  │   source_file: "helpful.md"}    │
  │ ────────────────────────────────►│
  │  ◄──── 200 OK                   │
```

---

## 11. Ollama Integration Layer

### 11.1 Client Types

mochi-server maintains three Ollama client types:

| Client | Use Case | Library |
|---|---|---|
| `OllamaClient` (sync) | Streaming chat, model listing, model details | `ollama.Client` |
| `AsyncOllamaClient` | Async operations, background tasks | `ollama.AsyncClient` |
| `AsyncInstructorOllamaClient` | Structured output (summaries) | `ollama_instructor.OllamaInstructorAsync` |

### 11.2 Key Operations

| Operation | Client | Method |
|---|---|---|
| List models (completion-capable only) | Sync | `list_models() -> list[ModelInfo]` |
| Show model details | Sync | `show_model_details(name) -> ShowResponse` |
| Streaming chat | Sync | `chat_stream(model, messages, tools?, think?, context_window?) -> Iterator[ChatResponse]` |
| Non-streaming chat | Sync | `chat(model, messages, tools?, think?, context_window?) -> ChatResponse` |
| Async streaming chat | Async | `chat_stream(...) -> AsyncIterator[ChatResponse]` |
| Async non-streaming chat | Async | `chat(...) -> ChatResponse` |
| Structured response | Instructor | `structured_response(model, messages, format) -> ChatResponse` |

### 11.3 Model Filtering

Only models with `"completion"` in their `capabilities` list are exposed. This is checked via `client.show(model).capabilities`.

### 11.4 Model Info

Each model exposes:
- `name`, `size_mb`, `format`, `family`, `parameter_size`, `quantization_level`
- `capabilities` (list of strings, e.g. `["completion", "tools"]`)
- `context_length` (extracted from `modelinfo["{family}.context_length"]`)

---

## 12. Session Management

### 12.1 Session Storage

Sessions are stored as JSON files in the configured `sessions_dir`:

```
{sessions_dir}/{session_id}.json
```

The JSON schema is as follows:
```json
{
  "metadata": {
    "session_id": "a1b2c3d4e5",
    "model": "qwen3:14b",
    "created_at": "...",
    "updated_at": "...",
    "message_count": 6,
    "summary": {"summary": "...", "topics": ["..."]},
    "summary_model": "qwen3:14b",
    "format_version": "1.3",
    "tool_settings": {"tools": [], "tool_group": null, "execution_policy": "always_confirm"},
    "agent_settings": {"enabled_agents": [], "selection_metadata": null},
    "context_window_config": {
      "dynamic_enabled": true,
      "current_window": 8192,
      "last_adjustment": "initial_setup",
      "adjustment_history": [],
      "manual_override": false
    }
  },
  "messages": [
    {"role": "system", "content": "...", "source_file": "helpful.md", "message_id": "...", "timestamp": "..."},
    {"role": "user", "content": "Hello", "message_id": "...", "timestamp": "..."},
    {"role": "assistant", "content": "Hi!", "model": "qwen3:14b", "message_id": "...", "timestamp": "...", "eval_count": 12, "prompt_eval_count": 45}
  ]
}
```

### 12.2 Session ID Generation

10-character hex string from `uuid.uuid4()`, e.g. `"a1b2c3d4e5"`.

### 12.3 Format Version Migration

The session loader must handle migration from older versions:
- **1.0 → 1.1:** Add `tool_settings` field
- **1.1 → 1.2:** Add `context_window_config` field
- **1.2 → 1.3:** Add `agent_settings` field

### 12.4 Message Editing

When a user message is edited:
1. The message content at the given index is updated.
2. All messages **after** that index are removed (truncated).
3. The session is saved.
4. The client can then send a new chat request to regenerate the response from the edited message.

### 12.5 Session CRUD

| Operation | Description |
|---|---|
| **Create** | Generate new session_id, initialize metadata, optionally add system prompt |
| **Read** | Load from JSON file, migrate if needed |
| **Update** | Update metadata (model switch, tool/agent settings changes), save |
| **Delete** | Remove JSON file from disk |
| **List** | Scan directory for `.json` files, load metadata, sort by `updated_at` desc |

---

## 13. Tool System

### 13.1 Overview

The tool system allows users to define Python functions that LLMs can invoke during conversations. Tools are placed in the configured `tools_dir`.

### 13.2 Directory Structure

```
{tools_dir}/
├── __init__.py          # Exports tools via __all__, defines groups
├── math_tools.py        # Module with math tool functions
├── utility_tools.py     # Module with utility tool functions
└── ...
```

### 13.3 Tool Requirements

Every tool function must:
1. Have **type hints** on all parameters and return type
2. Have a **docstring** (used for schema generation and description)
3. Return a **string** (for LLM consumption)

### 13.4 Tool Groups

Groups are defined in `__init__.py` using double-underscore variables:

```python
__math__ = ["add_numbers", "subtract_numbers", "multiply_numbers"]
__utilities__ = ["get_current_time", "flip_coin"]
```

### 13.5 Tool Discovery Service

- Scans `tools_dir/__init__.py` for `__all__` exports
- Validates each function (has docstring, is callable)
- Extracts tool groups from `__dunder__` variables
- Caches results (with `reload_tools()` to force re-discovery)

### 13.6 Tool Schema Service

- Converts Python functions to Ollama `Tool` objects using `ollama._utils.convert_function_to_tool`
- Caches converted schemas (keyed on `name + id(func)`)
- Extracts descriptions from docstrings using `ollama._utils._parse_docstring`

### 13.7 Tool Execution Service

- Executes tool functions with the provided arguments
- Respects execution policy (always_confirm, never_confirm, confirm_destructive)
- Returns `ToolExecutionResult(success, result, error_message, execution_time, tool_name)`
- Maintains execution history (last 100 executions)
- Provides execution statistics

### 13.8 Tool Execution in Chat Flow

When the LLM returns `tool_calls` in its response:

1. The assistant message (with `tool_calls`) is saved to the session.
2. Each tool call is executed (with optional confirmation).
3. Each tool response is saved as a `tool` role message with `tool_name`.
4. The conversation continues: a new chat request is sent with the updated message history (including tool results).
5. This may recurse if the LLM makes additional tool calls.

---

## 14. Agent System

### 14.1 Overview

Agents are specialized LLM personas with their own tools, system prompts, and persistent sessions. They are invoked by the main LLM as a single tool called `agent`.

### 14.2 Directory Structure

```
{agents_dir}/
├── coder/
│   ├── SKILL.md          # Frontmatter (description, model) + system prompt
│   ├── coder.py          # Tool implementations
│   └── __init__.py       # Exports tools via __all__
├── agent_builder/
│   ├── SKILL.md
│   ├── agent_builder.py
│   └── __init__.py
└── agent_chats/           # Agent session storage
    ├── b80fa657b0.json
    └── fe0394527d.json
```

### 14.3 SKILL.md Format

```markdown
---
description: Brief description for LLM selection
model: optional_model_name
---

System prompt content here...
```

- `description` (required): Used in the dynamic `agent` tool docstring so the main LLM knows which agent to pick.
- `model` (optional): If omitted or unavailable, falls back to the session's chat model.
- Everything after the frontmatter closing `---` is the system prompt.

### 14.4 Agent Discovery

An agent is **valid** if all three files exist and at least one tool is exported in `__all__`.

Discovery skips:
- Directories starting with `_` or `.`
- The `agent_chats` directory

### 14.5 Agent Tool Exposure

A single tool named `agent` is registered with the main LLM session. Its **docstring is dynamically generated** to list all enabled agents and their descriptions:

```
Delegate a task to a specialised agent.

Available agents:
  - coder: A coding agent with file system operations...
  - agent_builder: An agent specialized in creating new agents...

Args:
    agent (str): The name of the agent to invoke.
    instruction (str): A clear, detailed instruction.
    session_id (str): Optional session ID to continue a previous agent conversation.

Returns:
    str: The agent's response including its Session ID.
```

### 14.6 Two-Phase Execution Loop

**Phase 1 — Planning (no tools):**
1. Create or load agent `ChatSession` in `agent_chats/`.
2. Refresh system prompt from latest `SKILL.md`.
3. Add the LLM's instruction as a `user` message.
4. Append ephemeral planning prompt (not persisted).
5. Call Ollama **without** tools.
6. Save the planning response.

**Phase 2 — Execution (tools allowed, loop):**
1. Append ephemeral execution prompt (not persisted).
2. Call Ollama **with** the agent's tools.
3. If tool calls → execute, save, loop.
4. If no tool calls on first iteration → save response, loop again (handles LLMs that "announce" before acting).
5. If no tool calls on subsequent iterations → agent is done, break.

**Output:** Plain text starting with `Session ID: {id}`, followed by all agent messages, tool calls, and tool results since the instruction.

### 14.7 Agent Chat Sessions

- Stored in `{agents_dir}/agent_chats/{session_id}.json`
- Use the same `ChatSession` JSON schema as user-LLM sessions.
- The main LLM can continue an agent session by passing `session_id`.

### 14.8 System Prompt Refresh

On every agent invocation, the system prompt in the agent session is **replaced** with the latest content from `SKILL.md`. This ensures edits take effect immediately.

---

## 15. Context Window Management

### 15.1 Overview

The `DynamicContextWindowService` calculates optimal context window sizes for each request based on model capabilities and current token usage.

### 15.2 Key Decisions

| Reason | Description |
|---|---|
| `initial_setup` | First request — set initial context window based on model |
| `usage_threshold` | Usage exceeded threshold — increase window |
| `model_change` | Model was changed — recalculate for new model |
| `no_adjustment` | Current window is adequate |
| `manual_override` | User manually set context window |

### 15.3 Calculation Logic

1. Get model's max context length from `modelinfo`.
2. Use 90% of max as safe limit.
3. For new conversations, default to `min(safe_limit, 8192)`.
4. For ongoing conversations with token usage, ensure at least 50% buffer above current usage.
5. Track adjustments in session metadata `context_window_config.adjustment_history` (keep last 10).

### 15.4 Context Window in Requests

The calculated `context_window` is passed to Ollama as `options.num_ctx`.

---

## 16. Summarization Service

### 16.1 Overview

Automatic background summarization generates structured summaries of conversations using the `AsyncInstructorOllamaClient` for Pydantic-validated output.

### 16.2 Summary Model

```python
class ConversationSummary(BaseModel):
    summary: str   # 2-5 sentence summary
    topics: list[str]  # Topics discussed
```

### 16.3 Trigger Conditions

A summary update is triggered when:
- At least 2 messages exist in the session.
- The last message is from the assistant.
- The last assistant message has no `tool_calls` (i.e., it's a complete text response).

### 16.4 Model Selection for Summaries

Some models don't support structured output (listed in `constants.SUMMARY_UNSUPPORTED_MODELS`). When the chat model is unsupported:
1. Use the session's stored `summary_model` if available and supported.
2. Otherwise, the client must specify a summary model via the API.
3. If no suitable model is available, summarization is skipped.

### 16.5 Background Execution in mochi-server

Summarization runs as a **FastAPI background task** after each successful assistant response is saved.

```python
from fastapi import BackgroundTasks

@router.post("/chat/{session_id}/stream")
async def chat_stream(session_id: str, ..., background_tasks: BackgroundTasks):
    # ... handle chat ...
    background_tasks.add_task(maybe_update_summary, session, model)
```

---

## 17. System Prompt Management

### 17.1 Overview

System prompts are `.md` or `.txt` files stored in the configured `system_prompts_dir`.

### 17.2 Operations

| Operation | Description |
|---|---|
| **List** | Scan directory for `.md`/`.txt` files, return filename + preview + word count |
| **Read** | Return full content of a prompt file |
| **Create** | Write a new prompt file |
| **Update** | Overwrite an existing prompt file |
| **Delete** | Remove a prompt file |
| **Validate** | Ensure content is non-empty and not excessively long (< 10,000 chars) |

### 17.3 System Prompt in Sessions

- A system prompt is always the **first message** (index 0) with role `"system"`.
- It includes an optional `source_file` field tracking which file it came from.
- System prompts can be added, updated, or removed mid-session.
- Updating replaces the existing system message; removing deletes it.

---

## 18. Streaming & Real-Time Communication

### 18.1 SSE (Server-Sent Events)

mochi-server uses **SSE** via the `sse-starlette` package for streaming chat responses. SSE is chosen over WebSockets because:
- Simpler to implement and consume.
- Works with standard HTTP clients.
- Naturally fits the unidirectional streaming pattern of LLM responses.
- Built-in reconnection support in EventSource API.

### 18.2 SSE Implementation

```python
from sse_starlette.sse import EventSourceResponse

@router.post("/chat/{session_id}/stream")
async def chat_stream(session_id: str, request: ChatRequest):
    async def event_generator():
        # ... yield SSE events ...
        yield {"event": "content_delta", "data": json.dumps({"content": chunk})}
        yield {"event": "done", "data": json.dumps({"session_id": session_id})}

    return EventSourceResponse(event_generator())
```

### 18.3 Stream Interruption

Clients can cancel an SSE stream by closing the connection. The server detects this and:
1. Saves any accumulated partial response to the session.
2. Cleans up resources.

---

## 19. Error Handling

### 19.1 Error Response Format

All error responses follow a consistent format:

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session with ID 'xyz' not found.",
    "details": {}
  }
}
```

### 19.2 Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `SESSION_NOT_FOUND` | 404 | Session ID does not exist |
| `MODEL_NOT_FOUND` | 404 | Model is not available in Ollama |
| `TOOL_NOT_FOUND` | 404 | Tool name is not discovered |
| `AGENT_NOT_FOUND` | 404 | Agent name is not discovered |
| `AGENT_INVALID` | 422 | Agent exists but is invalid (missing files, etc.) |
| `PROMPT_NOT_FOUND` | 404 | System prompt file not found |
| `OLLAMA_UNREACHABLE` | 502 | Cannot connect to Ollama server |
| `OLLAMA_ERROR` | 502 | Ollama returned an error |
| `TOOL_EXECUTION_FAILED` | 500 | Tool execution raised an exception |
| `TOOL_EXECUTION_DENIED` | 403 | User denied tool execution |
| `TOOL_CONFIRMATION_TIMEOUT` | 408 | Tool confirmation timed out |
| `INVALID_MESSAGE_INDEX` | 400 | Message index out of range or not a user message |
| `VALIDATION_ERROR` | 422 | Request body validation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### 19.3 Ollama Error Propagation

When Ollama returns an error (e.g., model not loaded, context overflow), the error is caught and returned to the client with:
- The original Ollama error message.
- An appropriate HTTP status code (typically 502).

---

## 20. Testing Strategy

### 20.1 Test Layers

| Layer | What | How |
|---|---|---|
| **Unit tests** | Individual services (session, tool discovery, agent discovery, context window) | Mock Ollama client, mock file system |
| **Integration tests** | API endpoints via TestClient | Mock Ollama responses, real file I/O in temp dirs |
| **End-to-end tests** | Full flow with real Ollama (optional) | Requires running Ollama instance, marked as `@pytest.mark.e2e` |

### 20.2 Test Tooling

- **pytest** with **pytest-asyncio** for async test support
- **httpx** for async TestClient (FastAPI's recommended test client)
- **tmp_path** fixture for isolated session/tool/agent directories

### 20.3 Test Configuration

Tests use a separate `MochiServerSettings` with temp directories to avoid polluting real data:

```python
@pytest.fixture
def test_settings(tmp_path):
    return MochiServerSettings(
        data_dir=str(tmp_path),
        sessions_dir="sessions",
        tools_dir="tools",
        agents_dir="agents",
        system_prompts_dir="system_prompts",
    )
```

### 20.4 Mocking Ollama

For unit and integration tests, Ollama is mocked at the client level:

```python
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_ollama_client():
    client = MagicMock(spec=OllamaClient)
    client.list_models.return_value = [
        ModelInfo(name="test-model", size_mb=1000.0, capabilities=["completion", "tools"], context_length=8192)
    ]
    client.chat_stream.return_value = iter([
        ChatResponse(message=Message(role="assistant", content="Hello!"), done=False),
        ChatResponse(message=Message(role="assistant", content=""), done=True, eval_count=10, prompt_eval_count=20),
    ])
    return client

@pytest.fixture
def mock_async_instructor_client():
    client = AsyncMock(spec=AsyncInstructorOllamaClient)
    client.structured_response.return_value = ChatResponse(
        message=Message(role="assistant", content='{"summary": "Test summary", "topics": ["test"]}')
    )
    return client
```

---

## Appendix A: Summary of All SSE Event Types

| Event | Payload Fields | When Emitted |
|---|---|---|
| `content_delta` | `content`, `role` | Each text chunk from LLM |
| `thinking_delta` | `content` | Each thinking block chunk (when `think=true`) |
| `tool_call` | `tool_name`, `arguments`, `call_index` | LLM requests a tool (auto-execute policy) |
| `tool_call_confirmation_required` | `tool_name`, `arguments`, `call_index`, `confirmation_id` | LLM requests a tool (confirm policy) |
| `tool_result` | `tool_name`, `success`, `result`, `error_message`, `call_index` | After tool execution |
| `tool_continuation_start` | `message` | Before sending tool results back to LLM |
| `agent_start` | `agent_name`, `instruction` | Agent invocation begins |
| `agent_planning` | `content` | Agent planning phase content chunks |
| `agent_execution` | `content` | Agent execution phase content chunks |
| `agent_tool_call` | `agent_name`, `tool_name`, `arguments` | Agent calls one of its tools |
| `agent_tool_result` | `agent_name`, `tool_name`, `success`, `result` | Agent tool execution result |
| `agent_complete` | `agent_name`, `session_id`, `output` | Agent execution finished |
| `message_complete` | `message_id`, `model`, `eval_count`, `prompt_eval_count`, `context_window` | Full message metadata |
| `error` | `code`, `message`, `details` | An error occurred during streaming |
| `done` | `session_id` | Stream is complete |

---

## Appendix B: Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `MOCHI_HOST` | `127.0.0.1` | Server bind address |
| `MOCHI_PORT` | `8000` | Server bind port |
| `MOCHI_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MOCHI_DATA_DIR` | `.` | Base directory for all data |
| `MOCHI_SESSIONS_DIR` | `chat_sessions` | Session storage directory (relative to `DATA_DIR`) |
| `MOCHI_TOOLS_DIR` | `tools` | Tools directory (relative to `DATA_DIR`) |
| `MOCHI_AGENTS_DIR` | `agents` | Agents directory (relative to `DATA_DIR`) |
| `MOCHI_AGENT_CHATS_DIR` | `agents/agent_chats` | Agent chats directory (relative to `DATA_DIR`) |
| `MOCHI_SYSTEM_PROMPTS_DIR` | `system_prompts` | System prompts directory (relative to `DATA_DIR`) |
| `MOCHI_PLANNING_PROMPT_PATH` | `docs/agents/agent_prompt_planning.md` | Planning prompt file |
| `MOCHI_EXECUTION_PROMPT_PATH` | `docs/agents/agent_prompt_execution.md` | Execution prompt file |
| `MOCHI_SUMMARIZATION_ENABLED` | `true` | Enable background summarization |
| `MOCHI_SUMMARIZATION_INTERVAL_SECONDS` | `3` | Summarization check interval |
| `MOCHI_DYNAMIC_CONTEXT_WINDOW_ENABLED` | `true` | Enable dynamic context window |
| `MOCHI_LOG_LEVEL` | `INFO` | Logging level |
